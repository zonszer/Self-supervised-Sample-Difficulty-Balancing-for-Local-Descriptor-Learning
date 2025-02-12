import os
from copy import deepcopy
import random
import numpy as np
from PIL import Image
import torch
import torch.utils.data as data
from torchvision.datasets.utils import download_url, check_integrity
from torchvision.datasets.vision import VisionDataset
from torchvision import transforms
import torchvision.datasets as dset
from tqdm import tqdm
import random
import torch.nn.functional as F
import copy
import os
import time

import matplotlib.pyplot as plt


class PhotoTour(VisionDataset):
    """`Learning Local Image Descriptors Data <http://phototour.cs.washington.edu/patches/default.htm>`_ Dataset.


    Args:
        root (string): Root directory where images are.
        name (string): Name of the dataset to load.
        transform (callable, optional): A function/transform that  takes in an PIL image
            and returns a transformed version.
        download (bool, optional): If true, downloads the dataset from the internet and
            puts it in root directory. If dataset is already downloaded, it is not
            downloaded again.

    """
    urls = {
        'notredame_harris': [
            'http://matthewalunbrown.com/patchdata/notredame_harris.zip',
            'notredame_harris.zip',
            '69f8c90f78e171349abdf0307afefe4d'
        ],
        'yosemite_harris': [
            'http://matthewalunbrown.com/patchdata/yosemite_harris.zip',
            'yosemite_harris.zip',
            'a73253d1c6fbd3ba2613c45065c00d46'
        ],
        'liberty_harris': [
            'http://matthewalunbrown.com/patchdata/liberty_harris.zip',
            'liberty_harris.zip',
            'c731fcfb3abb4091110d0ae8c7ba182c'
        ],
        'notredame': [
            'http://icvl.ee.ic.ac.uk/vbalnt/notredame.zip',
            'notredame.zip',
            '509eda8535847b8c0a90bbb210c83484'
        ],
        'yosemite': [
            'http://icvl.ee.ic.ac.uk/vbalnt/yosemite.zip',
            'yosemite.zip',
            '533b2e8eb7ede31be40abc317b2fd4f0'
        ],
        'liberty': [
            'http://icvl.ee.ic.ac.uk/vbalnt/liberty.zip',
            'liberty.zip',
            'fdd9152f138ea5ef2091746689176414'
        ],
    }
    mean = {'notredame': 0.4854, 'yosemite': 0.4844, 'liberty': 0.4437,
            'notredame_harris': 0.4854, 'yosemite_harris': 0.4844, 'liberty_harris': 0.4437}
    std = {'notredame': 0.1864, 'yosemite': 0.1818, 'liberty': 0.2019,
           'notredame_harris': 0.1864, 'yosemite_harris': 0.1818, 'liberty_harris': 0.2019}
    lens = {'notredame': 468159, 'yosemite': 633587, 'liberty': 450092,
            'liberty_harris': 379587, 'yosemite_harris': 450912, 'notredame_harris': 325295}
    image_ext = 'bmp'
    info_file = 'info.txt'
    matches_files = 'm50_100000_100000_0.txt'

    def __init__(self, root, name, train=True, transform=None, download=False, norm=False):
        super(PhotoTour, self).__init__(root, transform=transform)
        self.name = name
        self.data_dir = os.path.join(self.root, name)
        self.data_down = os.path.join(self.root, '{}.zip'.format(name))
        self.data_file = os.path.join(self.root, '{}.pt'.format(name))

        self.train = train
        self.mean = self.mean[name]
        self.std = self.std[name]

        if download:
            self.download()

        if not self._check_datafile_exists():
            raise RuntimeError('Dataset not found.' +
                               ' You can use download=True to download it')

        # load the serialized data
        self.data, self.labels, self.matches = torch.load(self.data_file)
        if norm:
            self.data_file = os.path.join(self.root, '{}_norm.pt'.format(name))
            if os.path.exists(self.data_file):
                self.data, self.labels, self.matches = torch.load(self.data_file)
                print('norm is loading')
            else:
                self.data0 = self.data
                for i, image in tqdm(enumerate(self.data0)):
                    # pad = np.zeros([128,64])
                    # pad[0:64,:]=self.data0[i]
                    image = image * 1.0
                    mean_ = torch.mean(image)
                    std_ = torch.std(image)
                    image = (image - mean_) / std_
                    image = (image + 3) / 6 * 255
                    self.data[i] = image.type(torch.ByteTensor)
                    # pad[64:128,:]=self.data0[i]
                    # plt.imshow(pad)
                    # plt.savefig('ss.png')
                del self.data0
                torch.save((self.data, self.labels, self.matches), self.data_file)

    def __getitem__(self, index):
        """
        Args:
            index (int): Index

        Returns:
            tuple: (data1, data2, matches)
        """
        if self.train:
            data = self.data[index]
            if self.transform is not None:
                data = self.transform(data)
            return data
        m = self.matches[index]
        data1, data2 = self.data[m[0]], self.data[m[1]]
        if self.transform is not None:
            data1 = self.transform(data1.numpy())
            data2 = self.transform(data2.numpy())
        return data1, data2, m[2]

    def __len__(self):
        if self.train:
            return self.lens[self.name]
        return len(self.matches)

    def _check_datafile_exists(self):
        return os.path.exists(self.data_file)

    def _check_downloaded(self):
        return os.path.exists(self.data_dir)

    def download(self):
        if self._check_datafile_exists():
            print('# Found cached data {}'.format(self.data_file))
            return

        if not self._check_downloaded():
            # download files
            url = self.urls[self.name][0]
            filename = self.urls[self.name][1]
            md5 = self.urls[self.name][2]
            fpath = os.path.join(self.root, filename)

            download_url(url, self.root, filename, md5)

            print('# Extracting data {}\n'.format(self.data_down))

            import zipfile
            with zipfile.ZipFile(fpath, 'r') as z:
                z.extractall(self.data_dir)

            os.unlink(fpath)

        # process and save as torch files
        print('# Caching data {}'.format(self.data_file))

        dataset = (
            read_image_file(self.data_dir, self.image_ext,
                            self.lens[self.name]),
            read_info_file(self.data_dir, self.info_file),
            read_matches_files(self.data_dir, self.matches_files)
        )

        with open(self.data_file, 'wb') as f:
            torch.save(dataset, f)

    def extra_repr(self):
        return "Split: {}".format("Train" if self.train is True else "Test")


def read_image_file(data_dir, image_ext, n):
    """Return a Tensor containing the patches
    """

    def PIL2array(_img):
        """Convert PIL image type to numpy 2D array
        """
        return np.array(_img.getdata(), dtype=np.uint8).reshape(64, 64)

    def find_files(_data_dir, _image_ext):
        """Return a list with the file names of the images containing the patches
        """
        files = []
        # find those files with the specified extension
        for file_dir in os.listdir(_data_dir):
            if file_dir.endswith(_image_ext):
                files.append(os.path.join(_data_dir, file_dir))
        return sorted(files)  # sort files in ascend order to keep relations

    patches = []
    list_files = find_files(data_dir, image_ext)

    for fpath in list_files:
        img = Image.open(fpath)
        for y in range(0, 1024, 64):
            for x in range(0, 1024, 64):
                patch = img.crop((x, y, x + 64, y + 64))
                patches.append(PIL2array(patch))
    return torch.ByteTensor(np.array(patches[:n]))


def read_info_file(data_dir, info_file):
    """Return a Tensor containing the list of labels
       Read the file and keep only the ID of the 3D point.
    """
    labels = []
    with open(os.path.join(data_dir, info_file), 'r') as f:
        labels = [int(line.split()[0]) for line in f]
    return torch.LongTensor(labels)


def read_matches_files(data_dir, matches_file):
    """Return a Tensor containing the ground truth matches
       Read the file and keep only 3D point ID.
       Matches are represented with a 1, non matches with a 0.
    """
    matches = []
    with open(os.path.join(data_dir, matches_file), 'r') as f:
        for line in f:
            line_split = line.split()
            matches.append([int(line_split[0]), int(line_split[3]),
                            int(line_split[1] == line_split[4])])
    return torch.LongTensor(matches)


class TrainBatchPhotoTour(PhotoTour):
    """
    From the PhotoTour Dataset it generates triplet samples
    note: a triplet is composed by a pair of matching images and one of
    different class(https://github.com/DagnyT/hardnet).
    """

    def __init__(self, root, name, download=True, transform=None, Mode='pair', batch_size=1024,
                 num_triplets=500000, fliprot=True, norm=False):
        super(TrainBatchPhotoTour, self).__init__(root=root, name=name, download=download,
                                                  train=True, norm=norm)
        self.transform = transform
        self.Mode = Mode
        self.batch_size = batch_size
        self.n_triplets = num_triplets
        self.fliprot = fliprot
        self.indices = self.create_indices(self.labels.numpy())
        unique_labels = np.unique(self.labels.numpy())
        self.n_classes = unique_labels.shape[0]
        print('number of classes {}'.format(self.n_classes))
        print('number of patches {}'.format(self.data.shape[0]))
        self.labellist = None

    def create_indices(self, _labels):
        inds = dict()
        counter = 0
        counter1 = 0
        for idx, ind in enumerate(_labels):
            counter += 1
            if ind not in inds:
                inds[ind] = []
                if counter > 2:
                    counter1 += 1
                counter = 0
            inds[ind].append(idx)
        # print(counter1)
        return inds

    def generate_triplets(self, num_triplets, batch_size):
        # add only unique indices in batch
        already_idxs = set()
        triplets = []
        for x in range(num_triplets):
            if len(already_idxs) >= self.batch_size:
                already_idxs = set()
            c1 = np.random.randint(0, self.n_classes)
            while c1 in already_idxs:
                c1 = np.random.randint(0, self.n_classes)
            already_idxs.add(c1)
            c2 = np.random.randint(0, self.n_classes)
            while c1 == c2:
                c2 = np.random.randint(0, self.n_classes)
            if len(self.indices[c1]) == 2:  # hack to speed up process
                n1, n2 = 0, 1
            else:
                n1 = np.random.randint(0, len(self.indices[c1]))
                n2 = np.random.randint(0, len(self.indices[c1]))
                while n1 == n2:
                    n2 = np.random.randint(0, len(self.indices[c1]))
            n3 = np.random.randint(0, len(self.indices[c2]))
            triplets.append(
                [self.indices[c1][n1], self.indices[c1][n2], self.indices[c2][n3]])
        return torch.LongTensor(np.array(triplets))

    def generate_trainset(self, epoches):
        start = time.time()
        if not os.path.exists(self.root + '/' + self.name + '_train_triplets'):
            os.mkdir(self.root + '/' + self.name + '_train_triplets')
        for i in range(epoches):
            file_name = self.root + '/' + self.name + \
                        '_train_triplets/train_triplets_{}.pt'.format(i)
            if not os.path.exists(file_name):
                # print('Generating {} triplets'.format(self.n_triplets))
                self.triplets = self.generate_triplets(
                    self.n_triplets, self.batch_size)
                torch.save(self.triplets, file_name)
            print('save_{}_{}'.format(self.name, i))
        stop = time.time()
        print(stop - start)

    def generate_newdata(self, epoch=-1, epoches=500):
        if epoch < 0:
            epoch = np.random.randint(0, epoches)
        file_name = self.root + '/' + self.name + \
                    '_train_triplets/train_triplets_{}.pt'.format(epoch)
        if os.path.exists(file_name):
            print('Loading {} triplets'.format(self.n_triplets))
            self.triplets = torch.load(file_name)
            if not (self.triplets.size(0) == self.n_triplets):
                print('fail to load saved triplets')
            else:
                return
        print('Generating {} triplets'.format(self.n_triplets))
        self.triplets = self.generate_triplets(
            self.n_triplets, self.batch_size)

    def transform_img(self, img):
        if self.transform is not None:
            img = self.transform(img.numpy())
            return img
        return img.unsqueeze(0).float() / 255

    def __getitem__(self, index):
        out_triplets = self.Mode != 'pair'
        t = self.triplets[index]
        a, p, n = self.data[t[0]], self.data[t[1]], self.data[t[2]]

        img_a = self.transform_img(a)
        img_p = self.transform_img(p)
        if out_triplets:
            img_n = self.transform_img(n)
        if self.fliprot:
            flip_mode = np.random.randint(0, 3)
            rot_mode = np.random.randint(0, 4)
            img_a = self.rot(img_a, rot_mode)
            img_p = self.rot(img_p, rot_mode)
            img_a = self.flip(img_a, flip_mode)
            img_p = self.flip(img_p, flip_mode)
            if out_triplets:
                img_n = self.rot(img_n, rot_mode)
                img_n = self.flip(img_n, flip_mode)
        if out_triplets:
            return img_a, img_p, img_n
        else:
            return img_a, img_p

    def __len__(self):
        if self.train:
            return self.triplets.size(0)

    def rot(self, img, rot_mode):
        if rot_mode == 0:
            img = img.transpose(1, 2)
            img = img.flip(1)
        elif rot_mode == 1:
            img = img.flip(1)
            img = img.flip(2)
        elif rot_mode == 2:
            img = img.flip(1)
            img = img.transpose(1, 2)
        return img

    def flip(self, img, flip_mode):
        if flip_mode == 0:
            img = img.flip(1)
        elif flip_mode == 1:
            img = img.flip(2)
        return img


if __name__ == '__main__':
    # a = PhotoTour(root='/data1/ACuO/UBC/', name='liberty', norm=True)
    # del a
    c = PhotoTour(root='Datasets/6Brown', name='yosemite', norm=True, download=True)
    del c
    b = PhotoTour(root='Datasets/6Brown/new', name='liberty', norm=True, download=True)
    del b
    a = PhotoTour(root='Datasets/6Brown/new', name='notredame', norm=True, download=True)
    # c = PhotoTour(root='/data1/ACuO/UBC/', name='notredame', norm=True)
