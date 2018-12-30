import numpy as np
import cv2
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(os.path.join(parent_dir, 'tools'))
from pickle_dataset import merge_pickled_dictionaries

from sklearn.externals import joblib
"""
Adapted from https://github.com/kratzert/finetune_alexnet_with_tensorflow/blob/master/datagenerator.py
"""


class ImageDataGenerator:
    """ Set read_as_pickle as True to read file class_list as joblib file and
    therefore load images and labels. Set it to False to read file class_list as
    a file generated by split_dataset in split_dataset_with_labels_world.py
    [path_to_line center_of_line (3x) line_type label] on each line. """
    def __init__(self, class_list, horizontal_flip=False, shuffle=False, image_type='bgr', mean=np.array([22.47429166, 20.13914579, 5.62511388]), scale_size=(227, 227), read_as_pickle=False):
        # Init params
        self.horizontal_flip = horizontal_flip
        self.shuffle = shuffle
        self.image_type = image_type
        if image_type not in ['bgr', 'bgr-d']:
            raise ValueError("Images should be 'bgr' or 'bgr-d'")
        self.mean = mean
        self.scale_size = scale_size
        self.pointer = 0
        self.read_as_pickle = read_as_pickle

        if read_as_pickle:
            self.read_class_list_as_pickle(class_list)
        else:
            self.read_class_list_as_path_and_labels(class_list)

        if self.shuffle:
            self.shuffle_data()

    def read_class_list_as_pickle(self, class_list):
        """
        Load images and labels to memory from the joblib file
        """
        pickled_dict = {}
        # Merge dictionaries extracted from all the pickle files in class_list
        for file_ in class_list:
            temp_dict = joblib.load(file_)
            merge_pickled_dictionaries(pickled_dict, temp_dict)
        self.pickled_images_bgr = []
        self.pickled_images_depth = []
        self.pickled_labels = []
        self.line_types = []
        for dataset_name in pickled_dict.keys():
            dataset_name_dict = pickled_dict[dataset_name]
            for trajectory_number in dataset_name_dict.keys():
                trajectory_number_dict = dataset_name_dict[trajectory_number]
                for frame_number in trajectory_number_dict.keys():
                    frame_number_dict = trajectory_number_dict[frame_number]
                    for image_type in frame_number_dict.keys():
                        image_type_dict = frame_number_dict[image_type]
                        for line_number in image_type_dict.keys():
                            line_number_dict = image_type_dict[line_number]
                            # Append image
                            if image_type == 'rgb':
                                # Append label
                                self.pickled_labels.append(
                                    line_number_dict['labels'])
                                self.pickled_images_bgr.append(
                                    line_number_dict['img'])
                            elif image_type == 'depth':
                                self.pickled_images_depth.append(
                                    line_number_dict['img'])
                            # Append line type
                            self.line_types.append(
                                line_number_dict['line_type'])
            # store total number of data
        self.data_size = len(self.pickled_labels)
        self.access_indices = np.array(range(self.data_size))
        print('Just set data_size to be {0}'.format(self.data_size))

    def read_class_list_as_path_and_labels(self, class_list):
        """
        Scan the image file and get the image paths and labels
        """
        # In non-pickle mode read only first file in the list
        with open(class_list[0]) as f:
            lines = f.readlines()
            self.images = []
            self.labels = []
            self.line_types = []
            for l in lines:
                items = l.split()
                self.images.append(items[0])
                self.labels.append([float(i)
                                    for i in items[1:-2]] + [float(items[-1])])
                self.line_types.append(float(items[-2]))

            # store total number of data
            self.data_size = len(self.labels)

    def shuffle_data(self):
        """
        Random shuffle the images and labels
        """

        if self.read_as_pickle:
            # Indices that encode the order the dataset is accessed
            idx = np.random.permutation(len(self.pickled_labels))
            self.access_indices = idx
        else:
            images = list(self.images)
            labels = list(self.labels)
            line_types = list(self.line_types)
            self.images = []
            self.labels = []
            self.line_types = []
            idx = np.random.permutation(len(labels))

            for i in idx:
                self.images.append(images[i])
                self.labels.append(labels[i])
                self.line_types.append(line_types[i])

    def reset_pointer(self):
        """
        reset pointer to begin of the list
        """
        self.pointer = 0

        if self.shuffle:
            self.shuffle_data()

    def set_pointer(self, index):
        """
        set pointer to index of the list
        """
        self.pointer = index

    def next_batch(self, batch_size):
        """
        This function gets the next n ( = batch_size) images from the path list
        and labels and loads the images into them into memory
        """

        # Allocate memory for batch of images
        if self.image_type == 'bgr':
            images = np.ndarray(
                [batch_size, self.scale_size[0], self.scale_size[1], 3])
        elif self.image_type == 'bgr-d':
            images = np.ndarray(
                [batch_size, self.scale_size[0], self.scale_size[1], 4])

        if self.read_as_pickle:
            labels = []
            line_types = []
            # Get next batch of image (path) and labels
            for i in range(self.pointer, self.pointer + batch_size):
                idx = self.access_indices[i]
                #print('idx is {0}'.format(idx))
                if self.image_type == 'bgr':
                    # bgr image
                    img = self.pickled_images_bgr[idx]
                elif self.image_type == 'bgr-d':
                    img = np.dstack([
                        self.pickled_images_bgr[idx],
                        self.pickled_images_depth[idx]
                    ])
                # flip image at random if flag is selected
                if self.horizontal_flip and np.random.random() < 0.5:
                    img = cv2.flip(img, 1)

                # rescale image
                img = cv2.resize(img, (self.scale_size[0], self.scale_size[1]))
                img = img.astype(np.float32)

                # subtract mean
                img -= self.mean

                images[i - self.pointer] = img
                labels.append(self.pickled_labels[idx])
                line_types.append(self.line_types[idx])
        else:
            # Get next batch of image (path) and labels
            paths = self.images[self.pointer:self.pointer + batch_size]
            labels = self.labels[self.pointer:self.pointer + batch_size]
            line_types = self.line_types[self.pointer:self.pointer + batch_size]

            # Read images
            for i in range(len(paths)):
                if self.image_type == 'bgr':
                    # bgr image
                    img = cv2.imread(paths[i], cv2.IMREAD_UNCHANGED)
                elif self.image_type == 'bgr-d':
                    path_rgb = paths[i]
                    path_depth = path_rgb.replace('rgb', 'depth')
                    img_bgr = cv2.imread(path_rgb, cv2.IMREAD_UNCHANGED)
                    img_depth = cv2.imread(path_depth, cv2.IMREAD_UNCHANGED)
                    # bgr-d image
                    img = np.dstack([img_bgr, img_depth])

                # flip image at random if flag is selected
                if self.horizontal_flip and np.random.random() < 0.5:
                    img = cv2.flip(img, 1)

                # rescale image
                img = cv2.resize(img, (self.scale_size[0], self.scale_size[1]))
                img = img.astype(np.float32)

                # subtract mean
                img -= self.mean

                images[i] = img

        # Update pointer
        self.pointer += batch_size

        # To numpy array
        labels = np.array(labels, dtype=np.float32)
        line_types = np.asarray(
            line_types, dtype=np.float32).reshape(batch_size, -1)
        # Normalize line_types from values in {0, 1, 2, 3} to values in [-1, 1]:
        # - Zero-center by subtracting mean (1.5)
        # - Normalize the interval ([-1.5, 2.5]) to [-1, 1] (divide by 1.5)
        line_types = (line_types - 1.5) / 1.5
        if self.read_as_pickle:
            assert labels.shape == (batch_size, 7)
        else:
            assert labels.shape == (batch_size, 4)

        # return array of images, labels and line types
        return images, labels, line_types
