from torch import nn
from torchvision import models


class ResNetClassifier(nn.Module):
    def __init__(self, num_classes_per_category, dropout_rate=None):
        super(ResNetClassifier, self).__init__()
        base_model = models.resnet50(weights=models.ResNet50_Weights.DEFAULT) # :TODO wagi rozpoznawanie tekstu
        self.base_layers = nn.Sequential(*list(base_model.children())[:-1])

        self.dropout = nn.Dropout(dropout_rate) if dropout_rate is not None else nn.Identity()

        self.location_classifier = nn.Linear(base_model.fc.in_features, num_classes_per_category['location'])
        self.component_classifier = nn.Linear(base_model.fc.in_features, num_classes_per_category['component'])
        self.repair_type_classifier = nn.Linear(base_model.fc.in_features, num_classes_per_category['repair_type'])
        self.damage_classifier = nn.Linear(base_model.fc.in_features, num_classes_per_category['damage'])
        # :TODO one output class

    def forward(self, x):
        x = self.base_layers(x)
        x = x.view(x.size(0), -1)

        x = self.dropout(x)

        location = self.location_classifier(x)
        component = self.component_classifier(x)
        repair_type = self.repair_type_classifier(x)
        damage = self.damage_classifier(x)
        return location, component, repair_type, damage
