import paddle.v2 as paddle

from paddle.v2.attr import  Hook
from paddle.v2.attr import  ParamAttr

def conv_bn_layer(input,
                  ch_out,
                  filter_size,
                  stride,
                  padding,
                  active_type=paddle.activation.Relu(),
                  ch_in=None, param_attr=None):

    tmp = paddle.layer.img_conv(
        input=input,
        filter_size=filter_size,
        num_channels=ch_in,
        num_filters=ch_out,
        stride=stride,
        padding=padding,
        act=paddle.activation.Linear(),
        bias_attr=False,
        param_attr=param_attr)
    return paddle.layer.batch_norm(input=tmp, act=active_type)

def shortcut(input, ch_in, ch_out, stride):
    if ch_in != ch_out:
	    return conv_bn_layer(input, ch_out, 1, stride, 0, paddle.activation.Linear())
    else:
        return input

def basicblock(input, ch_in, ch_out, stride):
    short = shortcut(input, ch_in, ch_out, stride)
    param_attr = ParamAttr(update_hooks = Hook('dynamic_pruning', sparsity_upper_bound=0.8))
    conv1 = conv_bn_layer(input, ch_out, 3, stride, 1, param_attr=param_attr)
    conv2 = conv_bn_layer(conv1, ch_out, 3, 1, 1, paddle.activation.Linear())
    return paddle.layer.addto(
        input=[short, conv2], act=paddle.activation.Relu())

def layer_warp(block_func, input, ch_in, ch_out, count, stride):
    conv = block_func(input, ch_in, ch_out, stride)
    for i in range(1, count):
        conv = block_func(conv, ch_out, ch_out, 1)
    return conv

def resnet18(data_dim, class_dim, depth=18):
    input = paddle.layer.data(
        name="image", type=paddle.data_type.dense_vector(data_dim))
    cfg = {
        18: ([2, 2, 2, 2], basicblock),
    }
    stages, block_func = cfg[depth]
    conv1 = conv_bn_layer(
        input, ch_in=3, ch_out=64, filter_size=7, stride=2, padding=3)
    pool1 = paddle.layer.img_pool(input=conv1, pool_size=3, stride=2)
    res1 = layer_warp(block_func, pool1, 64, 64, stages[0], 1)
    res2 = layer_warp(block_func, res1, 64, 128, stages[1], 2)
    res3 = layer_warp(block_func, res2, 128, 256, stages[2], 2)
    res4 = layer_warp(block_func, res3, 256, 512, stages[3], 2)
    pool2 = paddle.layer.img_pool(
        input=res4, pool_size=7, stride=1, pool_type=paddle.pooling.Avg())

    out = paddle.layer.fc(name='resnetfc',
        input=pool2, size=class_dim, act=paddle.activation.Softmax(),
         param_attr = ParamAttr(update_hooks=Hook('dynamic_pruning',
                                 sparsity_upper_bound=0.9)))
    return out
