import time
import datetime
import os

import tensorflow.keras as tf_keras
import tensorflow as tf

import numpy as np
np.random.seed(123)

import model
import datagenerator_framewise

from datagenerator_framewise import LineDataSequence
from model import line_net_model_4
from model import image_pretrain_model
from inference import infer_on_test_set


class LayerUnfreezeCallback(tf_keras.callbacks.Callback):
    def __init__(self, loss, opt, metrics):
        super().__init__()

        self.loss = loss
        self.opt = opt
        self.metrics = metrics

    def on_epoch_end(self, epoch, logs=None):
        if epoch == 15:
            transfer_layers = ["block3_conv1", "block3_conv2", "block3_conv3"]
            for layer_name in transfer_layers:
                self.model.get_layer("image_features").get_layer("vgg16_features").get_layer(layer_name).trainable = \
                    True
                print("Unfreezing layer {}.".format(layer_name))

            self.model.compile(loss=self.loss,
                               optimizer=self.opt,
                               metrics=self.metrics,
                               experimental_run_tf_function=False)

        if epoch == 30:
            transfer_layers = ["block2_conv1", "block2_conv2"]
            for layer_name in transfer_layers:
                self.model.get_layer("image_features").get_layer("vgg16_features").get_layer(layer_name).trainable = \
                    True
                print("Unfreezing layer {}.".format(layer_name))

            self.model.compile(loss=self.loss,
                               optimizer=self.opt,
                               metrics=self.metrics,
                               experimental_run_tf_function=False)


class LearningRateCallback(tf_keras.callbacks.Callback):
    def __init__(self, decay):
        super().__init__()
        self.decay = decay

    def on_epoch_begin(self, epoch, logs=None):
        for key in sorted(self.decay.keys()):
            if epoch >= key:
                print("Setting learning rate to {}.".format(self.decay[key]))
                self.model.optimizer.learning_rate = self.decay[key]

        if epoch + 1 in self.decay:
            print("Setting learning rate to {}.".format(self.decay[epoch + 1]))
            self.model.optimizer.learning_rate = self.decay[epoch + 1]


class InferenceCallback(tf_keras.callbacks.Callback):
    def __init__(self, test_dir, log_dir, bg_classes, img_shape, max_line_count, max_clusters):
        super().__init__()

        self.test_dir = test_dir
        self.log_dir = log_dir
        self.bg_classes = bg_classes
        self.img_shape = img_shape
        self.max_line_count = max_line_count
        self.max_clusters = max_clusters

    def on_epoch_end(self, epoch, logs=None):
        print("Inference on test set.")
        infer_on_test_set(self.model, self.test_dir, self.log_dir, epoch + 1, self.bg_classes, self.img_shape,
                          self.max_line_count, self.max_clusters)
        print("Inference done.")


class SaveCallback(tf_keras.callbacks.Callback):
    def __init__(self, path, cluster=False):
        super().__init__()
        self.path = path
        self.cluster = cluster

    def on_epoch_end(self, epoch, logs=None):
        model.save_line_net_model(self.model, self.path.format(epoch + 1))


def train_cluster():
    physical_devices = tf.config.list_physical_devices('GPU')
    tf.config.experimental.set_memory_growth(physical_devices[0], True)

    # Paths to line files.
    train_files = "/nvme/line_ws/train"
    val_files = "/nvme/line_ws/val"
    test_files = "/nvme/line_ws/test"

    line_num_attr = 15
    img_shape = (64, 96, 3)
    min_line_count = 4
    max_line_count = 50
    batch_size = 3
    num_epochs = 40
    margin = 0.6
    embedding_dim = 256
    # max_clusters = 15
    bg_classes = [0, 1, 2, 20, 22]
    # valid_classes = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 25, 30]
    valid_classes = [i for i in range(41) if i not in bg_classes]
    num_classes = 1 + len(valid_classes)
    image_weight_path = "/home/felix/line_ws/src/line_tools/python/line_net/weights/image_weights.hdf5"

    load_past = True
    past_epoch = 12
    log_path = "/home/felix/line_ws/src/line_tools/python/line_net/logs/description_040620_1846"

    if not load_past:
        cluster_model = model.cluster_triplet_loss_model(line_num_attr, max_line_count, embedding_dim,
                                                         img_shape, margin)
        cluster_model.get_layer("cluster_embedding_model").get_layer("image_features").load_weights(image_weight_path)
    else:
        load_path = os.path.join(log_path, "weights_only.{:02d}.hdf5".format(past_epoch))
        cluster_model = model.load_cluster_triplet_model(load_path, line_num_attr, max_line_count, embedding_dim,
                                                         img_shape, margin)
    cluster_model.summary()
    # cluster_model.optimizer.learning_rate = 0.000025

    train_data_generator = datagenerator_framewise.ClusterDataSequence(train_files,
                                                                       batch_size,
                                                                       bg_classes,
                                                                       valid_classes,
                                                                       shuffle=True,
                                                                       data_augmentation=True,
                                                                       img_shape=img_shape,
                                                                       min_line_count=min_line_count,
                                                                       max_line_count=max_line_count)

    val_data_generator = datagenerator_framewise.ClusterDataSequence(val_files,
                                                                     batch_size,
                                                                     bg_classes,
                                                                     valid_classes,
                                                                     shuffle=False,
                                                                     data_augmentation=False,
                                                                     img_shape=img_shape,
                                                                     min_line_count=min_line_count,
                                                                     max_line_count=max_line_count)

    if not load_past:
        log_path = "./logs/description_{}".format(datetime.datetime.now().strftime("%d%m%y_%H%M"))
    tensorboard_callback = tf_keras.callbacks.TensorBoard(log_dir=log_path)
    save_callback = SaveCallback(os.path.join(log_path, "weights_only.{:02d}.hdf5"), cluster=True)
    learning_rate_callback = LearningRateCallback({5: 0.00005, 10: 0.000025, 20: 0.00001})
    callbacks = [tensorboard_callback, save_callback, learning_rate_callback]

    initial_epoch = 0
    if load_past:
        initial_epoch = past_epoch
    cluster_model.fit(x=train_data_generator,
                      verbose=1,
                      max_queue_size=16,
                      workers=1,
                      epochs=num_epochs,
                      # steps_per_epoch=10,
                      # validation_steps=10,
                      initial_epoch=initial_epoch,
                      use_multiprocessing=True,
                      validation_data=val_data_generator,
                      callbacks=callbacks)


def train():
    physical_devices = tf.config.list_physical_devices('GPU')
    tf.config.experimental.set_memory_growth(physical_devices[0], True)

    # Paths to line files.
    train_files = "/nvme/line_ws/train"
    val_files = "/nvme/line_ws/val"
    test_files = "/nvme/line_ws/test"

    # The length of the geometry vector of a line.
    line_num_attr = 15
    img_shape = (64, 96, 3)
    max_line_count = 160
    batch_size = 2
    num_epochs = 40
    # Do not forget to delete pickle files when this config is changed.
    max_clusters = 15
    # TODO: Check if 0 is background or naw.
    bg_classes = [0, 1, 2, 20, 22]
    load_past = True
    past_epoch = 10
    past_path = "/home/felix/line_ws/src/line_tools/python/line_net/logs/cluster_060620_0111"
    image_weight_path = "/home/felix/line_ws/src/line_tools/python/line_net/weights/image_weights.hdf5"

    pretrain_images = False

    # Create line net Keras model.
    if pretrain_images:
        line_model, loss, opt, metrics = image_pretrain_model(line_num_attr, max_line_count, img_shape)
    else:
        line_model, loss, opt, metrics = line_net_model_4(line_num_attr, max_line_count, max_clusters, img_shape)
        line_model.get_layer("image_features").summary()
        line_model.get_layer("image_features").load_weights(image_weight_path)
    line_model.summary()

    if load_past:
        log_path = past_path
        for layer in line_model.layers:
            layer.trainable = False
        line_model.load_weights(os.path.join(log_path, "weights_only.{:02d}.hdf5".format(past_epoch)),
                                by_name=True)
        for layer in line_model.layers:
            layer.trainable = True
        line_model.get_layer("image_features").trainable = False
    else:
        log_path = "./logs/cluster_{}".format(datetime.datetime.now().strftime("%d%m%y_%H%M"))

    # train_set_mean = np.array([-0.00246431839, 0.0953982015,  3.15564408])

    train_data_generator = LineDataSequence(train_files,
                                            batch_size,
                                            bg_classes,
                                            shuffle=True,
                                            fuse=False,
                                            img_shape=img_shape,
                                            min_line_count=30,
                                            max_line_count=max_line_count,
                                            data_augmentation=True,
                                            max_cluster_count=max_clusters)
    # train_set_mean = train_data_generator.get_mean()
    # train_data_generator.set_mean(train_set_mean)
    # print("Train set mean is: {}".format(train_set_mean))
    val_data_generator = LineDataSequence(val_files,
                                          batch_size,
                                          bg_classes,
                                          fuse=False,
                                          img_shape=img_shape,
                                          min_line_count=30,
                                          max_line_count=max_line_count,
                                          max_cluster_count=max_clusters)

    save_weights_callback = tf_keras.callbacks.ModelCheckpoint(os.path.join(log_path, "weights.{epoch:02d}.hdf5"))
    tensorboard_callback = tf_keras.callbacks.TensorBoard(log_dir=log_path, write_graph=False, write_images=True)
    save_callback = SaveCallback(os.path.join(log_path, "weights_only.{:02d}.hdf5"))
    inference_callback = InferenceCallback(test_files, log_path, bg_classes, img_shape, max_line_count, max_clusters)
    learning_rate_callback = LearningRateCallback({10: 0.000025, 15: 0.00001, 20: 0.000005})
    callbacks = [save_weights_callback, tensorboard_callback, save_callback, inference_callback, learning_rate_callback]
    if pretrain_images:
        unfreeze_callback = LayerUnfreezeCallback(loss, opt, metrics)
        callbacks += [unfreeze_callback]

    initial_epoch = 0
    if load_past:
        initial_epoch = past_epoch
    line_model.fit(x=train_data_generator,
                   verbose=1,
                   max_queue_size=16,
                   workers=4,
                   epochs=num_epochs,
                   # steps_per_epoch=10,
                   # validation_steps=10,
                   initial_epoch=initial_epoch,
                   use_multiprocessing=True,
                   validation_data=val_data_generator,
                   callbacks=callbacks)


if __name__ == '__main__':
    train()
    # train_cluster()




