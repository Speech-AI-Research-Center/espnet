import asteroid_filterbanks.transforms as af_transforms
import torch
from asteroid.masknn import activations


class Conv2DActNorm(torch.nn.Module):
    def __init__(
        self,
        in_channels,
        out_channels,
        ksz=(3, 3),
        stride=(1, 2),
        padding=(1, 0),
        upsample=False,
        activation=torch.nn.ELU,
    ):
        super(Conv2DActNorm, self).__init__()

        if upsample:
            conv = torch.nn.ConvTranspose2d(
                in_channels, out_channels, ksz, stride, padding
            )
        else:
            conv = torch.nn.Conv2d(
                in_channels, out_channels, ksz, stride, padding, padding_mode="reflect"
            )
        act = activations.get(activation)()
        norm = torch.nn.GroupNorm(out_channels, out_channels, eps=1e-8)
        self.layer = torch.nn.Sequential(conv, act, norm)

    def forward(self, inp):
        return self.layer(inp)


class FreqWiseBlock(torch.nn.Module):
    def __init__(self, in_channels, num_freqs, out_channels, activation=torch.nn.ELU):
        super(FreqWiseBlock, self).__init__()

        self.bottleneck = Conv2DActNorm(
            in_channels, out_channels, (1, 1), (1, 1), (0, 0), activation=activation
        )
        self.freq_proc = Conv2DActNorm(
            num_freqs, num_freqs, (1, 1), (1, 1), (0, 0), activation=activation
        )

    def forward(self, inp):
        # bsz, chans, x, y

        out = self.freq_proc(self.bottleneck(inp).permute(0, 3, 2, 1)).permute(
            0, 3, 2, 1
        )

        return out


class DenseBlock(torch.nn.Module):
    def __init__(
        self,
        in_channels,
        out_channels,
        num_freqs,
        pre_blocks=2,
        freq_proc_blocks=1,
        post_blocks=2,
        ksz=(3, 3),
        activation=torch.nn.ELU,
        hid_chans=32,
    ):

        super(DenseBlock, self).__init__()

        assert post_blocks >= 1
        assert pre_blocks >= 1

        self.pre_blocks = torch.nn.ModuleList([])
        tot_layers = 0
        for indx in range(pre_blocks):
            c_layer = Conv2DActNorm(
                in_channels + hid_chans * tot_layers,
                hid_chans,
                ksz,
                (1, 1),
                (1, 1),
                activation=activation,
            )
            self.pre_blocks.append(c_layer)
            tot_layers += 1

        self.freq_proc_blocks = torch.nn.ModuleList([])
        for indx in range(freq_proc_blocks):
            c_layer = FreqWiseBlock(
                in_channels + hid_chans * tot_layers,
                num_freqs,
                hid_chans,
                activation=activation,
            )
            self.freq_proc_blocks.append(c_layer)
            tot_layers += 1

        self.post_blocks = torch.nn.ModuleList([])
        for indx in range(post_blocks - 1):
            c_layer = Conv2DActNorm(
                in_channels + hid_chans * tot_layers,
                hid_chans,
                ksz,
                (1, 1),
                (1, 1),
                activation=activation,
            )
            self.post_blocks.append(c_layer)
            tot_layers += 1

        last = Conv2DActNorm(
            in_channels + hid_chans * tot_layers,
            out_channels,
            ksz,
            (1, 1),
            (1, 1),
            activation=activation,
        )
        self.post_blocks.append(last)

    def forward(self, input):

        out = [input]
        for pre_block in self.pre_blocks:
            c_out = pre_block(torch.cat(out, 1))
            out.append(c_out)

        for freq_block in self.freq_proc_blocks:
            c_out = freq_block(torch.cat(out, 1))
            out.append(c_out)

        for post_block in self.post_blocks:
            c_out = post_block(torch.cat(out, 1))
            out.append(c_out)

        return c_out


class TCNResBlock(torch.nn.Module):
    def __init__(
        self, in_chan, out_chan, ksz=3, stride=1, dilation=1, activation=torch.nn.ELU
    ):
        super(TCNResBlock, self).__init__()
        padding = dilation
        dconv = torch.nn.Conv1d(
            in_chan,
            in_chan,
            ksz,
            stride,
            padding=padding,
            dilation=dilation,
            padding_mode="reflect",
            groups=in_chan,
        )
        point_conv = torch.nn.Conv1d(in_chan, out_chan, 1)

        self.layer = torch.nn.Sequential(
            torch.nn.GroupNorm(in_chan, in_chan, eps=1e-8),
            activations.get(activation)(),
            dconv,
            point_conv,
        )

    def forward(self, inp):
        return self.layer(inp) + inp


class TCNDenseUNet(torch.nn.Module):
    def __init__(
        self,
        n_spk=1,
        in_channels=257,
        mic_channels=1,
        hid_chans=32,
        hid_chans_dense=32,
        ksz_dense=(3, 3),
        ksz_tcn=3,
        tcn_repeats=4,
        tcn_blocks=7,
        tcn_channels=384,
        activation=torch.nn.ELU,
    ):
        super(TCNDenseUNet, self).__init__()
        self.n_spk = n_spk
        self.in_channels = in_channels
        self.mic_channels = mic_channels

        num_freqs = in_channels - 2
        first = torch.nn.Sequential(
            torch.nn.Conv2d(
                self.mic_channels * 2,
                hid_chans,
                (3, 3),
                (1, 1),
                (1, 0),
                padding_mode="reflect",
            ),
            DenseBlock(
                hid_chans,
                hid_chans,
                num_freqs,
                ksz=ksz_dense,
                activation=activation,
                hid_chans=hid_chans_dense,
            ),
        )

        freq_axis_dims = self._get_depth(num_freqs)
        self.encoder = torch.nn.ModuleList([])
        self.encoder.append(first)

        for layer_indx in range(len(freq_axis_dims)):
            downsample = Conv2DActNorm(
                hid_chans, hid_chans, (3, 3), (1, 2), (1, 0), activation=activation
            )
            denseblocks = DenseBlock(
                hid_chans,
                hid_chans,
                freq_axis_dims[layer_indx],
                ksz=ksz_dense,
                activation=activation,
                hid_chans=hid_chans_dense,
            )
            c_layer = torch.nn.Sequential(downsample, denseblocks)
            self.encoder.append(c_layer)

        self.encoder.append(
            Conv2DActNorm(
                hid_chans, hid_chans * 2, (3, 3), (1, 2), (1, 0), activation=activation
            )
        )
        self.encoder.append(
            Conv2DActNorm(
                hid_chans * 2,
                hid_chans * 4,
                (3, 3),
                (1, 2),
                (1, 0),
                activation=activation,
            )
        )
        self.encoder.append(
            Conv2DActNorm(
                hid_chans * 4,
                tcn_channels,
                (3, 3),
                (1, 1),
                (1, 0),
                activation=activation,
            )
        )

        self.tcn = []
        for r in range(tcn_repeats):
            for x in range(tcn_blocks):
                self.tcn.append(
                    TCNResBlock(
                        tcn_channels,
                        tcn_channels,
                        ksz_tcn,
                        dilation=2**x,
                        activation=activation,
                    )
                )

        self.tcn = torch.nn.Sequential(*self.tcn)
        self.decoder = torch.nn.ModuleList([])
        self.decoder.append(
            Conv2DActNorm(
                tcn_channels * 2,
                hid_chans * 4,
                (3, 3),
                (1, 1),
                (1, 0),
                activation=activation,
                upsample=True,
            )
        )
        self.decoder.append(
            Conv2DActNorm(
                hid_chans * 8,
                hid_chans * 2,
                (3, 3),
                (1, 2),
                (1, 0),
                activation=activation,
                upsample=True,
            )
        )
        self.decoder.append(
            Conv2DActNorm(
                hid_chans * 4,
                hid_chans,
                (3, 3),
                (1, 2),
                (1, 0),
                activation=activation,
                upsample=True,
            )
        )

        for dec_indx in range(len(freq_axis_dims)):
            c_num_freqs = freq_axis_dims[len(freq_axis_dims) - dec_indx - 1]
            denseblocks = DenseBlock(
                hid_chans * 2,
                hid_chans * 2,
                c_num_freqs,
                ksz=ksz_dense,
                activation=activation,
                hid_chans=hid_chans_dense,
            )
            upsample = Conv2DActNorm(
                hid_chans * 2,
                hid_chans,
                (3, 3),
                (1, 2),
                (1, 0),
                activation=activation,
                upsample=True,
            )
            c_layer = torch.nn.Sequential(denseblocks, upsample)
            self.decoder.append(c_layer)

        last = torch.nn.Sequential(
            DenseBlock(
                hid_chans * 2,
                hid_chans * 2,
                self.in_channels - 2,
                ksz=ksz_dense,
                activation=activation,
                hid_chans=hid_chans_dense,
            ),
            torch.nn.ConvTranspose2d(
                hid_chans * 2, 2 * self.n_spk, (3, 3), (1, 1), (1, 0)
            ),
        )
        self.decoder.append(last)

    def _get_depth(self, num_freq):

        n_layers = 0
        freqs = []
        while num_freq > 15:
            num_freq = int(num_freq / 2)
            freqs.append(num_freq)
            n_layers += 1
        return freqs

    def forward(self, tf_rep):
        # B, T, C, F
        tf_rep = tf_rep.permute(0, 2, 3, 1)
        bsz, mics, _, frames = tf_rep.shape
        assert mics == self.mic_channels

        inp_feats = af_transforms.to_torch_complex(tf_rep)
        inp_feats = torch.cat((inp_feats.real, inp_feats.imag), 1)
        inp_feats = inp_feats.transpose(-1, -2)
        inp_feats = inp_feats.reshape(
            bsz, self.mic_channels * 2, frames, self.in_channels
        )

        enc_out = []
        buffer = inp_feats
        for enc_layer in self.encoder:
            buffer = enc_layer(buffer)
            enc_out.append(buffer)

        assert buffer.shape[-1] == 1
        tcn_out = self.tcn(buffer.squeeze(-1)).unsqueeze(-1)

        buffer = tcn_out
        for indx, dec_layer in enumerate(self.decoder):
            c_input = torch.cat((buffer, enc_out[-(indx + 1)]), 1)
            buffer = dec_layer(c_input)

        if self.n_spk > 1:
            buffer = buffer.reshape(bsz, 2, self.n_spk, -1, self.in_channels)
        out = torch.cat((buffer[:, 0], buffer[:, 1]), -1)
        # bsz, complex_chans, frames or bsz, spk, complex_chans, frames
        return out.transpose(1, 2)  # bsz, spk, time, freq -> bsz, time, spk, freq
