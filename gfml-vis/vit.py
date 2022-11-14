import torch
import torch.nn as nn
import torchsummary

from layers import TransformerEncoder

import wormhole

class ViT(nn.Module):
    def __init__(self, in_c: int = 3, num_classes: int = 10, img_size: int = 32, patch: int = 8, dropout: float = 0.,
                 num_layers: int = 7, hidden: int = 384, mlp_hidden: int = 384 * 4, head: int = 8,
                 is_cls_token: bool = True, qk_mode=None):
        super(ViT, self).__init__()

        self.patch = patch # number of patches in one row(or col)
        self.is_cls_token = is_cls_token
        self.patch_size = img_size//self.patch
        f = (img_size//self.patch)**2*3 # 48 # patch vec length
        num_tokens = (self.patch**2)+1 if self.is_cls_token else (self.patch**2)

        if wormhole.mass_pos in ['head', 'tail', 'full_fix']:
            self.mass_q = nn.Embedding(num_tokens, 1)
            self.mass_k = nn.Embedding(num_tokens, 1)
            nn.init.uniform_(self.mass_q.weight)
            nn.init.uniform_(self.mass_k.weight)

        self.emb = nn.Linear(f, hidden) # (b, n, f)
        self.cls_token = nn.Parameter(torch.randn(1, 1, hidden)) if is_cls_token else None
        self.pos_emb = nn.Parameter(torch.randn(1, num_tokens, hidden))
        # enc_list = [TransformerEncoder(hidden, mlp_hidden=mlp_hidden, dropout=dropout, head=head, num_tokens = num_tokens, qk_mode=qk_mode, mass_q=self.mass_q, mass_k=self.mass_k) for _ in range(num_layers)]

        enc_list = []
        for i in range(num_layers):
            if wormhole.mass_pos == 'head' and i == 0:
                enc_list.append(
                    TransformerEncoder(hidden, mlp_hidden=mlp_hidden, dropout=dropout, head=head, num_tokens=num_tokens,
                                       qk_mode=qk_mode, mass_q=self.mass_q, mass_k=self.mass_k))
            elif wormhole.mass_pos == 'tail' and i == (num_layers -1):
                enc_list.append(
                    TransformerEncoder(hidden, mlp_hidden=mlp_hidden, dropout=dropout, head=head, num_tokens=num_tokens,
                                       qk_mode=qk_mode, mass_q=self.mass_q, mass_k=self.mass_k))
            elif wormhole.mass_pos == 'full_fix':
                enc_list.append(
                    TransformerEncoder(hidden, mlp_hidden=mlp_hidden, dropout=dropout, head=head, num_tokens=num_tokens,
                                       qk_mode=qk_mode, mass_q=self.mass_q, mass_k=self.mass_k))
            else:
                enc_list.append(
                    TransformerEncoder(hidden, mlp_hidden=mlp_hidden, dropout=dropout, head=head, num_tokens=num_tokens,
                                       qk_mode=qk_mode))

        self.enc = nn.Sequential(*enc_list)
        self.fc = nn.Sequential(
            nn.LayerNorm(hidden),
            nn.Linear(hidden, num_classes) # for cls_token
        )

    def forward(self, x):
        out = self._to_words(x)
        out = self.emb(out)
        if self.is_cls_token:
            out = torch.cat([self.cls_token.repeat(out.size(0),1,1), out],dim=1)
        out = out + self.pos_emb
        out = self.enc(out)
        if self.is_cls_token:
            out = out[:, 0]
        else:
            out = out.mean(1)
        out = self.fc(out)
        return out

    def _to_words(self, x):
        """
        (b, c, h, w) -> (b, n, f)
        """
        out = x.unfold(2, self.patch_size, self.patch_size).unfold(3, self.patch_size, self.patch_size).permute(0,2,3,4,5,1)
        out = out.reshape(x.size(0), self.patch**2 ,-1)
        return out


if __name__ == "__main__":
    b,c,h,w = 4, 3, 32, 32
    x = torch.randn(b, c, h, w)
    net = ViT(in_c=c, num_classes= 10, img_size=h, patch=16, dropout=0.1, num_layers=7, hidden=384, head=12, mlp_hidden=384, is_cls_token=False)
    # out = net(x)
    # out.mean().backward()
    torchsummary.summary(net, (c,h,w))
    # print(out.shape)
    