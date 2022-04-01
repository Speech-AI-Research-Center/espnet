import pytest
import torch

from espnet2.asr.specaug.specaug import SpecAug
from espnet2.asr.transducer.decoder.rnn_decoder import RNNDecoder
from espnet2.asr.transducer.decoder.stateless_decoder import StatelessDecoder
from espnet2.asr.transducer.encoder.encoder import Encoder
from espnet2.asr.transducer.espnet_transducer_model import ESPnetASRTransducerModel
from espnet2.asr.transducer.joint_network import JointNetwork


def prepare(model, input_size, vocab_size, batch_size):
    n_token = vocab_size - 1

    feat_len = [15, 11]
    label_len = [13, 9]

    feats = torch.randn(batch_size, max(feat_len), input_size)
    labels = (torch.rand(batch_size, max(label_len)) * n_token % n_token).long()

    for i in range(2):
        feats[i, feat_len[i] :] = model.ignore_id
        labels[i, label_len[i] :] = model.ignore_id
    labels[labels == 0] = vocab_size - 2

    return feats, labels, torch.tensor(feat_len), torch.tensor(label_len)


def get_decoder(vocab_size, params):
    if "rnn_type" in params:
        decoder = RNNDecoder(vocab_size, **params)
    else:
        decoder = StatelessDecoder(vocab_size, **params)

    return decoder


def get_specaug():
    return SpecAug(
        apply_time_warp=True,
        apply_freq_mask=True,
        apply_time_mask=False,
    )


@pytest.mark.parametrize(
    "enc_params, dec_params, joint_net_params, main_params",
    [
        (
            [{"block_type": "rnn", "dim_hidden": 4}],
            {"rnn_type": "lstm", "num_layers": 2},
            {"dim_joint_space": 4},
            {"report_cer": True, "report_wer": True},
        ),
        (
            [{"block_type": "rnn", "dim_hidden": 4}],
            {"dim_embedding": 4},
            {"dim_joint_space": 4},
            {"specaug": True},
        ),
        (
            [{"block_type": "rnn", "dim_hidden": 4}],
            {"dim_embedding": 4},
            {"dim_joint_space": 4},
            {"auxiliary_ctc_weight": 0.1, "auxiliary_lm_loss_weight": 0.1},
        ),
        (
            [{"block_type": "conformer", "dim_hidden": 4, "dim_linear": 4}],
            {"dim_embedding": 4},
            {"dim_joint_space": 4},
            {"auxiliary_ctc_weight": 0.1, "auxiliary_lm_loss_weight": 0.1},
        ),
    ],
)
def test_model_training(enc_params, dec_params, joint_net_params, main_params):
    batch_size = 2
    input_size = 10

    token_list = ["<blank>", "a", "b", "c", "<space>"]
    vocab_size = len(token_list)

    encoder = Encoder(input_size, enc_params)
    decoder = get_decoder(vocab_size, dec_params)

    joint_network = JointNetwork(
        vocab_size, encoder.dim_output, decoder.dim_output, **joint_net_params
    )

    specaug = get_specaug() if main_params.pop("specaug", False) else None

    model = ESPnetASRTransducerModel(
        vocab_size,
        token_list,
        frontend=None,
        specaug=specaug,
        normalize=None,
        encoder=encoder,
        decoder=decoder,
        joint_network=joint_network,
        **main_params,
    )

    feats, labels, feat_len, label_len = prepare(
        model, input_size, vocab_size, batch_size
    )

    _ = model(feats, feat_len, labels, label_len)

    if main_params.get("report_cer") or main_params.get("report_wer"):
        model.training = False

        _ = model(feats, feat_len, labels, label_len)


@pytest.mark.parametrize("extract_feats", [True, False])
def test_collect_feats(extract_feats):
    token_list = ["<blank>", "a", "b", "c", "<space>"]
    vocab_size = len(token_list)

    encoder = Encoder(20, [{"block_type": "rnn", "dim_hidden": 4}])
    decoder = StatelessDecoder(vocab_size, dim_embedding=4)

    joint_network = JointNetwork(vocab_size, encoder.dim_output, decoder.dim_output, 8)

    model = ESPnetASRTransducerModel(
        vocab_size,
        token_list,
        frontend=None,
        specaug=None,
        normalize=None,
        encoder=encoder,
        decoder=decoder,
        joint_network=joint_network,
    )
    model.extract_feats_in_collect_stats = extract_feats

    feats_dict = model.collect_feats(
        torch.randn(2, 12),
        torch.tensor([12, 11]),
        torch.randn(2, 8),
        torch.tensor([8, 8]),
    )

    assert set(("feats", "feats_lengths")) == feats_dict.keys()
