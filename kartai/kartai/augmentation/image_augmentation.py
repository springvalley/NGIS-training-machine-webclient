# -*- coding: utf-8 -*-
"""
Created on Thu Apr 22 08:05:35 2021

@author: stipav
"""
# https://dbuscombe-usgs.github.io/MLMONDAYS/blog/2020/10/23/blog-post.html

from typing import List
import numpy as np
import sys
from numpy import expand_dims
from tensorflow.keras.preprocessing.image import load_img
from tensorflow.keras.preprocessing.image import img_to_array
from tensorflow.keras.preprocessing.image import ImageDataGenerator

import datetime
import random
import math
import os
from osgeo import gdal


def augment_it(image_path: str, label_path: str, augment_size: int, augment_seed: int = -1, save_to_disk: str = None, dataset_id: str = 'anonymous_dataset') -> List[np.array]:
    """ 
    Creates augmented set from the images pair (image / label).
    Augmented set is saved in the folder if save_to_disk parameter is specified.    
    If dataset_id is provided result is saved under save_to_disk/dataset_id folder.
    For the same augment_seed value the same augmentation transformation is applied.
    If ommited augment_seed is auto generated.
    \n
    Saved images are georeferenced but some of them are flipped!!!
    
    Parameters
    ----------       
    image_path : str
        full path to the image
        
    label_path : str
        full path to the image label
        
    augment_size : int
        number of augmented images to generate
        
    augment_seed : int = -1
        random seed for transformation applied during the augmentation    
        the value is autgenerated when ommited
        
    save_to_disk: str = None
        save augmented images to the folder save_to_disk
        if ommited augmented images are not saved to the disk
        
    dataset_id : str = anonymous_dataset
        subfolder to save_to_disk.
    
    Returns
    -------
    List[np.array]
    list of augmented pairs [image, label]
    """

    #generate seed
    augment_seed = augment_seed
    
    # if augment_seed is not provided the value is autogenerated
    if augment_seed == -1:
        ts = datetime.datetime.now().timestamp()
        random.seed(ts, version=2)
        max_seed = 1000000000
        augment_seed = random.randint(0, max_seed)    

    image = load_img(image_path)
    label = load_img(label_path)
    
    data_image = img_to_array(image)
    data_label = img_to_array(label)

    samples_image = expand_dims(data_image, 0)
    samples_label = expand_dims(data_label, 0)

    # more testning needed here to get the best or better augmentation setup
    data_gen_args_image = dict(
        #width_shift_range=[-100, 100],
        #height_shift_range=[-100, 100],
        #rotation_range=45,
        #channel_shift_range = 2,
        horizontal_flip=True,
        vertical_flip=True,
        brightness_range=[0.5, 2],
        fill_mode="constant",
        cval=120
    )
    
    # keep only relevant trnsformations for the labels: horisontal and vertical flip, rotation, shift... and similar
    data_gen_args_label = data_gen_args_image.copy()
    for di in data_gen_args_image:
        if di not in ['horizontal_flip','vertical_flip','rotation_range', 'width_shift_range', 'height_shift_range']:
            data_gen_args_label.pop(di)
    
    image_data_gen = ImageDataGenerator(**data_gen_args_image)
    label_data_gen = ImageDataGenerator(**data_gen_args_label)
    
    
    batch_size = 1
    if save_to_disk is not None:
        aug_image_path = os.path.join(save_to_disk, dataset_id, 'image')
        aug_label_path = os.path.join(save_to_disk, dataset_id, 'label')
    
        if not os.path.exists(aug_image_path):
            os.makedirs(aug_image_path)
        
        if not os.path.exists(aug_label_path):
            os.makedirs(aug_label_path)        
        
        aug_prefix_image = os.path.splitext(os.path.basename(image_path))[0]
        aug_prefix_label = os.path.splitext(os.path.basename(label_path))[0]
        
        it_image = image_data_gen.flow(samples_image, batch_size=batch_size, seed=augment_seed, save_to_dir=aug_image_path, save_prefix = aug_prefix_image )
        it_label = label_data_gen.flow(samples_label, batch_size=batch_size, seed=augment_seed, save_to_dir=aug_label_path, save_prefix = aug_prefix_label )
        
    else:
        it_image = image_data_gen.flow(samples_image, batch_size=batch_size, seed=augment_seed)
        it_label = label_data_gen.flow(samples_label, batch_size=batch_size, seed=augment_seed)
        
    it_image = image_data_gen.flow(samples_image, batch_size=batch_size, seed=augment_seed)
    it_label = label_data_gen.flow(samples_label, batch_size=batch_size, seed=augment_seed)        

    
    # save augmented images / labels in list
    augment_images = []
    augment_labels = []
    for i in range(augment_size):
        augment_images.append(it_image.next())
        augment_labels.append(it_label.next())
        
    if save_to_disk is not None:
        
        # get transform and projection params from the image that is subject to augmetation
        source_img = gdal.Open(image_path)
        transform = source_img.GetGeoTransform()
        projection = source_img.GetProjection()
        rows = source_img.RasterYSize
        cols = source_img.RasterXSize        
        source_img = None        
        
        #implement naming convention based on provided params 
        aug_image_path = os.path.join(save_to_disk, dataset_id, 'image')
        aug_label_path = os.path.join(save_to_disk, dataset_id, 'label')
    
        if not os.path.exists(aug_image_path):
            os.makedirs(aug_image_path)
        
        if not os.path.exists(aug_label_path):
            os.makedirs(aug_label_path)        
        
        aug_prefix_image = os.path.splitext(os.path.basename(image_path))[0]
        aug_prefix_label = os.path.splitext(os.path.basename(label_path))[0]
        
        for i in range(augment_size):
            image_name = aug_prefix_image + '_{0:03d}.tif'.format(i)
            label_name = aug_prefix_label + '_{0:03d}.tif'.format(i)
            
            image_name = os.path.join(aug_image_path,image_name)
            label_name = os.path.join(aug_label_path,label_name)
            
            write_aug_image_pair(cols, rows, transform, projection, augment_images[i], augment_labels[i],image_name, label_name )

    return [augment_images, augment_labels]


def write_aug_image_pair(cols: int, rows: int, transform: tuple, projection: str, image: np.array, label: np.array, image_name: str, label_name: str):
    
    target_img = gdal.GetDriverByName('GTiff').Create(image_name,  cols, rows, 3, gdal.GDT_Byte, ['COMPRESS=JPEG','PHOTOMETRIC=YCBCR'])
    target_img.SetGeoTransform(transform)
    target_img.SetProjection(projection)    
    
    target_img.GetRasterBand(1).SetColorInterpretation(gdal.GCI_RedBand)
    target_img.GetRasterBand(2).SetColorInterpretation(gdal.GCI_GreenBand)
    target_img.GetRasterBand(3).SetColorInterpretation(gdal.GCI_BlueBand)
    
    target_lbl = gdal.GetDriverByName('GTiff').Create(label_name, cols, rows, 1, gdal.GDT_Byte,  ['COMPRESS=LZW', 'PREDICTOR=2'])
    target_lbl.SetGeoTransform(transform)
    target_lbl.SetProjection(projection)   

    target_lbl.GetRasterBand(1).SetColorInterpretation(gdal.GCI_GrayIndex)     
    
    
    for band_id in range(3):
        img_band = np.transpose(image[0])[band_id]
        target_img.GetRasterBand(band_id + 1).WriteArray(img_band)
        
    band_id = 0
    lbl_band = np.transpose(label[0])[band_id]
    target_lbl.GetRasterBand(band_id + 1).WriteArray(lbl_band)
    
    target_img.FlushCache()    
    target_lbl.FlushCache()    
    
    del target_img
    del target_lbl    