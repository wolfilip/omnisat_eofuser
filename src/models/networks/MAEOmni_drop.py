import torch
from torch import nn


class MAEUnival(nn.Module):
    """
    Masked Autoencoder part for OmniSat pretraining with token dropping instead of masked token learned
    """
    def __init__(self, 
                 encoder, 
                 decoder, 
                 embed_dim: int = 256,
                ):
        super().__init__()
        # --------------------------------------------------------------------------
        # MAE encoder specifics
        self.encoder = encoder
        # --------------------------------------------------------------------------
        # MAE decoder specifics

        self.decoder = decoder
        # --------------------------------------------------------------------------
        self.embed_dim = embed_dim

    def _init_weights(self, m):
        if isinstance(m, nn.Linear):
            # we use xavier_uniform following official JAX ViT:
            torch.nn.init.xavier_uniform_(m.weight)
            if isinstance(m, nn.Linear) and m.bias is not None:
                nn.init.constant_(m.bias, 0)
        elif isinstance(m, nn.LayerNorm):
            nn.init.constant_(m.bias, 0)
            nn.init.constant_(m.weight, 1.0)

    def random_masking(self, x, mask_ratio):
        """
        Perform per-sample random masking by per-sample shuffling.
        Per-sample shuffling is done by argsort random noise.
        x: [N, L, D], sequence
        """
        N, L, D = x.shape  # batch, length, dim
        len_keep = int(L * (1 - mask_ratio))
        
        noise = torch.rand(N, L, device=x.device)  # noise in [0, 1]
        
        # sort noise for each sample
        ids_shuffle = torch.argsort(noise, dim=1)  # ascend: small is keep, large is remove
        ids_restore = torch.argsort(ids_shuffle, dim=1)

        # keep the first subset
        ids_keep = ids_shuffle[:, :len_keep]
        x_masked = torch.gather(x, dim=1, index=ids_keep.unsqueeze(-1).repeat(1, 1, D))

        # generate the binary mask: 0 is keep, 1 is remove
        mask = torch.ones([N, L], device=x.device)
        mask[:, :len_keep] = 0

        # unshuffle to get the binary mask
        mask = torch.gather(mask, dim=1, index=ids_restore)
        return x_masked, mask, ids_restore

    def forward_encoder(self, x, mask_ratio):
        tokens, out = self.encoder.forward_proj(x)
        tokens, mask, ids_restore = self.random_masking(tokens, mask_ratio)
        tokens = self.encoder.forward_transformer(tokens, mask)
        out['mm_tokens'] = tokens
        return out, mask

    def forward_decoder(self, out):
        # embed tokens
        x = self.decoder(out['mm_tokens'][:, 1:, :], out)
        return x

    def forward(self, imgs, mask_ratio=0.75):
        latent, mask = self.forward_encoder(imgs, mask_ratio)
        pred = self.forward_decoder(latent)
        return pred, mask
