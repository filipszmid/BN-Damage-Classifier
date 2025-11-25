import json

from PIL import Image
from torch.utils.data import Dataset

class ContainerDamageDataset(Dataset):
    def __init__(self, dataframe, encoder, transform=None):
        self.dataframe = dataframe
        self.transform = transform
        self.encoder = encoder

    def __len__(self):
        return len(self.dataframe)

    def __getitem__(self, idx):
        row = self.dataframe.iloc[idx]
        image = Image.open(row['processed_row']).convert('RGB')
        if self.transform:
            image = self.transform(image)

        metadata = json.loads(row['metadata'])
        loc_label, comp_label, rep_type_label, damage_label = self.encoder.encode(
            metadata['location'],
            metadata['component'],
            metadata['repair_type'],
            metadata['damage']
        )
        return image, (loc_label, comp_label, rep_type_label, damage_label)

    def _load_image(self, image_path):
        """
        Load the image from the filesystem.
        """
        image = Image.open(image_path)
        return image.convert('RGB')
