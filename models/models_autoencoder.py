import torch
import torch.nn as nn
import torch.nn.functional as F

class ConvConditionalVAE(nn.Module):
    def __init__(self, latent_dim=128, num_classes=7):
        super(ConvConditionalVAE, self).__init__()
        self.latent_dim = latent_dim
        self.num_classes = num_classes

        # ENCODER: riceve immagine + etichetta one-hot come canali extra
        # Input: (B, 3 + num_classes, 256, 256)
        self.encoder_conv = nn.Sequential(
            nn.Conv2d(3 + num_classes, 32, kernel_size=4, stride=2, padding=1), # -> (B, 32, 128, 128)
            nn.ReLU(),
            nn.BatchNorm2d(32),

            nn.Conv2d(32, 64, kernel_size=4, stride=2, padding=1),              # -> (B, 64, 64, 64)
            nn.ReLU(),
            nn.BatchNorm2d(64),

            nn.Conv2d(64, 128, kernel_size=4, stride=2, padding=1),             # -> (B, 128, 32, 32)
            nn.ReLU(),
            nn.BatchNorm2d(128),

            nn.Conv2d(128, 256, kernel_size=4, stride=2, padding=1),            # -> (B, 256, 16, 16)
            nn.ReLU(),
            nn.BatchNorm2d(256),

            nn.Flatten() # -> (B, 256*16*16)
        )

        self.flatten_dim = 256 * 16 * 16
        self.fc_mu = nn.Linear(self.flatten_dim, latent_dim)     # Media della distribuzione latente
        self.fc_logvar = nn.Linear(self.flatten_dim, latent_dim) # Log-varianza della distribuzione latente

        # DECODER: ricostruisce l'immagine a partire da z + label
        self.decoder_input = nn.Linear(latent_dim + num_classes, self.flatten_dim)  # -> (B, 256*16*16)

        self.decoder_conv = nn.Sequential(
            nn.Unflatten(1, (256, 16, 16)), # -> (B, 256, 16, 16)

            nn.ConvTranspose2d(256, 128, kernel_size=4, stride=2, padding=1), # -> (B, 128, 32, 32)
            nn.ReLU(),
            nn.BatchNorm2d(128),

            nn.ConvTranspose2d(128, 64, kernel_size=4, stride=2, padding=1),  # -> (B, 64, 64, 64)
            nn.ReLU(),
            nn.BatchNorm2d(64),

            nn.ConvTranspose2d(64, 32, kernel_size=4, stride=2, padding=1),   # -> (B, 32, 128, 128)
            nn.ReLU(),
            nn.BatchNorm2d(32),

            nn.ConvTranspose2d(32, 3, kernel_size=4, stride=2, padding=1),    # -> (B, 3, 256, 256)
            nn.Tanh()  # Normalizza l'output tra -1 e 1
        )

    def one_hot(self, labels, device):
        # Converte le etichette in one-hot
        return F.one_hot(labels, num_classes=self.num_classes).float().to(device)

    def encode(self, x, labels):
        label_map = self.one_hot(labels, x.device).unsqueeze(2).unsqueeze(3) 
        label_map = label_map.expand(-1, -1, x.size(2), x.size(3))           
        x_concat = torch.cat([x, label_map], dim=1)

        # Passa attraverso l'encoder
        h = self.encoder_conv(x_concat)
        mu = self.fc_mu(h)
        logvar = self.fc_logvar(h)
        logvar = torch.clamp(logvar, min=-10, max=10)
        return mu, logvar

    def reparameterize(self, mu, logvar):
        # Reparametrizzazione: z = mu + std * eps
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)  # Campionamento casuale standard
        return mu + eps * std

    def decode(self, z, labels):
        # Concatena z con le etichette one-hot
        z_cat = torch.cat([z, self.one_hot(labels, z.device)], dim=1)
        h = self.decoder_input(z_cat)
        x_reconstructed = self.decoder_conv(h)
        return x_reconstructed

    def forward(self, x, labels):
        """
        Esegue un forward pass completo:
        - codifica l'immagine e l'etichetta
        - campiona dallo spazio latente
        - decodifica per ottenere la ricostruzione

        Returns:
            x_reconstructed: immagine ricostruita
            mu, logvar: parametri della distribuzione latente
            z: variabile latente campionata
        """
        mu, logvar = self.encode(x, labels)
        z = self.reparameterize(mu, logvar)
        x_reconstructed = self.decode(z, labels)
        return x_reconstructed, mu, logvar, z
