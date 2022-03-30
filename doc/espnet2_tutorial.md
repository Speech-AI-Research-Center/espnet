# ESPnet2
We are planning a super major update, called `ESPnet2`. The developing status is still **under construction** yet, so please be very careful to use with understanding following cautions:

- There might be fatal bugs related to essential parts.
- We haven't achieved comparable results to espnet1 on each task yet.

## Main changing from ESPnet1

- **Chainer free**
  - Discarding Chainer completely.
  - The development of Chainer is stopped at v7: https://chainer.org/announcement/2019/12/05/released-v7.html
- **Kaldi free**
   - It's not mandatory to compile Kaldi.
   - **If you find some recipes requiring Kaldi mandatory, please report it. It should be dealt with as a bug in ESPnet2.**
   - We still support the features made by Kaldi optionally.
   - We still follow Kaldi style. i.e. depending on `utils/` of Kaldi.
- **On the fly** feature extraction & text preprocessing for training
   - You don't need to create the feature file before training, but just input wave data directly.
   - We support both raw wave input and extracted features.
   - The preprocessing for text, tokenization to characters, or sentencepieces, can be also applied during training.
   - Support **self-supervised learning representations** from s3prl
- Discarding the JSON format describing the training corpus.
   - Why do we discard the JSON format? Because a dict object generated from a large JSON file requires much memory and it also takes much time to parse such a large JSON file.
- Support distributed data-parallel training (Not enough tested)
   - Single node multi GPU training with `DistributedDataParallel` is also supported.

## Recipes using ESPnet2

You can find the new recipes in `egs2`:

```
espnet/  # Python modules of espnet1
espnet2/ # Python modules of espnet2
egs/     # espnet1 recipes
egs2/    # espnet2 recipes
```

The usage of recipes is **almost the same** as that of ESPnet1.


1. Change directory to the base directory

    ```bash
    # e.g.
    cd egs2/an4/asr1/
    ```
    `an4` is a tiny corpus and can be freely obtained, so it might be suitable for this tutorial. 
    You can perform any other recipes as the same way. e.g. `wsj`, `librispeech`, and etc.

    Keep in mind that all scripts should be ran at the level of `egs2/*/{asr1,tts1,...}`.
    
    ```bash
    # Doesn't work
    cd egs2/an4/
    ./asr1/run.sh
    ./asr1/scripts/<some-script>.sh
    
    # Doesn't work
    cd egs2/an4/asr1/local/
    ./data.sh
    
    # Work
    cd egs2/an4/asr1
    ./run.sh
    ./scripts/<some-script>.sh
    ```
    
1. Change the configuration
    Describing the directory structure as follows:
    
    ```
    egs2/an4/asr1/
     - conf/      # Configuration files for training, inference, etc.
     - scripts/   # Bash utilities of espnet2
     - pyscripts/ # Python utilities of espnet2
     - steps/     # From Kaldi utilities
     - utils/     # From Kaldi utilities
     - db.sh      # The directory path of each corpora
     - path.sh    # Setup script for environment variables
     - cmd.sh     # Configuration for your backend of job scheduler
     - run.sh     # Entry point
     - asr.sh     # Invoked by run.sh
    ```

    - You need to modify `db.sh` for specifying your corpus before executing `run.sh`. For example, when you touch the recipe of `egs2/wsj`, you need to change the paths of `WSJ0` and `WSJ1` in `db.sh`.
    - Some corpora can be freely obtained from the WEB and they are written as "downloads/" at the initial state. You can also change them to your corpus path if it's already downloaded.
    - `path.sh` is used to set up the environment for `run.sh`. Note that the Python interpreter used for ESPnet is not the current Python of your terminal, but it's the Python which was installed at `tools/`. Thus you need to source `path.sh` to use this Python.
        ```bash
        . path.sh
        python
        ```
    - `cmd.sh` is used for specifying the backend of the job scheduler. If you don't have such a system in your local machine environment, you don't need to change anything about this file. See [Using Job scheduling system](./parallelization.md)

1. Run `run.sh`

    ```bash
    ./run.sh
    ```

    `run.sh` is an example script, which we often call as "recipe", to run all stages related to DNN experiments; data-preparation, training, and evaluation.

## See training status

### Show the log file

```bash
% tail -f exp/*_train_*/train.log
[host] 2020-04-05 16:34:54,278 (trainer:192) INFO: 2/40epoch started. Estimated time to finish: 7 minutes and 58.63 seconds
[host] 2020-04-05 16:34:56,315 (trainer:453) INFO: 2epoch:train:1-10batch: iter_time=0.006, forward_time=0.076, loss=50.873, los
s_att=35.801, loss_ctc=65.945, acc=0.471, backward_time=0.072, optim_step_time=0.006, lr_0=1.000, train_time=0.203
[host] 2020-04-05 16:34:58,046 (trainer:453) INFO: 2epoch:train:11-20batch: iter_time=4.280e-05, forward_time=0.068, loss=44.369
, loss_att=28.776, loss_ctc=59.962, acc=0.506, backward_time=0.055, optim_step_time=0.006, lr_0=1.000, train_time=0.173
```

### Show the training status in a image file

```bash
# Accuracy plot
# (eog is Eye of GNOME Image Viewer)
eog exp/*_train_*/images/acc.img
# Attention plot
eog exp/*_train_*/att_ws/<sample-id>/<param-name>.img
```

### Use tensorboard

```sh
tensorboard --logdir exp/*_train_*/tensorboard/
```

# Instruction for run.sh
## How to parse command-line arguments in shell scripts?

All shell scripts in espnet/espnet2 depend on [utils/parse_options.sh](https://github.com/kaldi-asr/kaldi/blob/master/egs/wsj/s5/utils/parse_options.sh) to parase command line arguments.

e.g. If the script has `ngpu` option

```sh
#!/usr/bin/env bash
# run.sh
ngpu=1
. utils/parse_options.sh
echo ${ngpu}
```

Then you can change the value as follows:

```sh
$ ./run.sh --ngpu 2
echo 2
```

You can also show the help message:

```sh
./run.sh --help
```

## Start from a specified stage and stop at a specified stage
The procedures in `run.sh` can be divided into some stages, e.g. data preparation, training, and evaluation. You can specify the starting stage and the stopping stage.

```sh
./run.sh --stage 2 --stop-stage 6
```

There are also some altenative otpions to skip specified stages:

```sh
run.sh --skip_data_prep true  # Skip data preparation stages.
run.sh --skip_train true      # Skip training stages.
run.sh --skip_eval true       # Skip decoding and evaluation stages.
run.sh --skip_upload false    # Enable packing and uploading stages.
```

Note that `skip_upload` is true by default. Please change it to false when uploading your model.

## Change the configuration for training
Please keep in mind that `run.sh` is a wrapper script of several tools including DNN training command. 
You need to do one of the following two ways to change the training configuration. 

```sh
# Give a configuration file
./run.sh --asr_config conf/train_asr.yaml
# Give arguments to "espnet2/bin/asr_train.py" directly
./run.sh --asr_args "--foo arg --bar arg2"
```

e.g. To change learning rate for the LM training

```sh
./run.sh --lm_args "--optim_conf lr=0.1"
```

This is the case of ASR training and you need to replace it accordingly for the other task. e.g. For TTS

```sh
./run.sh --tts_args "--optim_conf lr=0.1"
```

See [Change the configuration for training](./espnet2_training_option.md) for more detail about the usage of training tools.


## Change the number of parallel jobs

```sh
./run.sh --nj 10             # Chnage the number of parallels for data preparation stages.
./run.sh --inference_nj 10   # Chnage the number of parallels for inference jobs.
```

We also support submitting jobs to multiple hosts to accelerate your experiment: See [Using Job scheduling system](./parallelization.md)


## Multi GPUs training and distributed training

```sh
./run.sh --ngpu 4 # 4GPUs in a single node
./run.sh --ngpu 2 --num_nodes 2 # 2GPUs x 2nodes
```


Note that you need to setup your environment correctly to use distributed training. See the following two:

- [Distributed training](./espnet2_distributed.md)
- [Using Job scheduling system](./parallelization.md)

## Use specified experiment directory for evaluation

If you already have trained a model, you may wonder how to give it to run.sh when you'll evaluate it later.
By default the directory name is determined according to given options, `asr_args`, `lm_args`, or etc.
You can overwrite it by `--asr_exp` and `--lm_exp`.

```sh
# For ASR recipe
./run.sh --skip_data_prep true --skip_train true --asr_exp <your_asr_exp_directory> --lm_exp <your_lm_exp_directory>

# For TTS recipe
./run.sh --skip_data_prep true --skip_train true --tts_exp <your_tts_exp_directory>
```

## Evaluation without training using pretrained model


```sh
./run.sh --download_model <model_name> --skip_train true
```

You need to fill `model_name` by yourself. You can search for pretrained models on Hugging Face using the tag [espnet](https://huggingface.co/models?library=espnet)

(Deprecated: See the following link about our pretrain models: https://github.com/espnet/espnet_model_zoo)

## Packing and sharing your trained model

ESPnet encourages you to share your results using platforms like [Hugging Face](https://huggingface.co/) or [Zenodo](https://zenodo.org/) (This last will become deprecated.)

For sharing your models, the last three stages of each task simplify this process. The model is packed into a zip file and uploaded to the selected platform (one or both).

For **Hugging Face**, you need to first create a repository (`<my_repo> = <user_name>/<repo_name>`).  
Remember to install `git-lfs ` before continuing.
Then, execute `run.sh` as follows:

```sh
# For ASR recipe
./run.sh --stage 14 --skip-upload-hf false --hf-repo <my_repo>

# For TTS recipe
./run.sh --stage 8 --skip-upload-hf false --hf-repo <my_repo>
```

For **Zenodo**, you need to register your account first. Then, execute `run.sh` as follows:

```sh
# For ASR recipe
./run.sh --stage 14 --skip-upload false

# For TTS recipe
./run.sh --stage 8 --skip-upload false
```

The packed model can be uploaded to both platforms by setting the previously mentioned flags.

## Usage of Self-Supervised Learning Representations as feature

ESPnet supports self-supervised learning representations (SSLR) to replace traditional spectrum features. In some cases, SSLRs can boost the performance.

To use SSLRs in your task, you need to make several modifications.

### Prerequisite
1. Install [S3PRL](https://github.com/s3prl/s3prl) by `tools/installers/install_s3prl.sh`.
2. If HuBERT / Wav2Vec is needed, [fairseq](https://github.com/pytorch/fairseq) should be installed by `tools/installers/install_fairseq.sh`.

### Usage
1. To reduce the time used in `collect_stats` step, please specify `--feats_normalize uttmvn` in `run.sh` and pass it as arguments to `asr.sh` or other task-specific scripts. (Recommended)
2. In the configuration file, specify the `frontend` and `preencoder`. Taking `HuBERT` as an example:
   The `upstream` name can be whatever supported in S3PRL. `multilayer-feature=True` means the final representation is a weighted-sum of all layers' hidden states from SSLR model.
   ```
   frontend: s3prl
   frontend_conf:
      frontend_conf:
         upstream: hubert_large_ll60k  # Note: If the upstream is changed, please change the input_size in the preencoder.
      download_dir: ./hub
      multilayer_feature: True
   ```
   Here the `preencoder` is to reduce the input dimension to the encoder, to reduce the memory cost. The `input_size` depends on the upstream model, while the `output_size` can be set to any values.
   ```
   preencoder: linear
   preencoder_conf:
      input_size: 1024  # Note: If the upstream is changed, please change this value accordingly.
      output_size: 80
   ```
3. Because the shift sizes of different `upstream` models are different, e.g. `HuBERT` and `Wav2Vec2.0` have `20ms` frameshift. Sometimes, the downsampling rate (`input_layer`) in the `encoder` configuration need to be changed. For example, using `input_layer: conv2d2` will results in a total frameshift of `40ms`, which is enough for some tasks.

## Streaming ASR
ESPnet supports streaming Transformer/Conformer ASR with blockwise synchronous beam search.

For more details, please refer to the [paper](https://arxiv.org/pdf/2006.14941.pdf).

### Training

To achieve streaming ASR, please employ blockwise Transformer/Conformer encoder in the configuration file. Taking `blockwise Transformer` as an example:
The `encoder` name can be `contextual_block_transformer` or `contextual_block_conformer`. 

```sh
encoder: contextual_block_transformer
encoder_conf:
    block_size: 40         # block size for block processing
    hop_size: 16           # hop size for block processing
    look_ahead: 16         # look-ahead size for block processing
    init_average: true     # whether to use average input as initial context 
    ctx_pos_enc: true      # whether to use positional encoding for the context vectors 
```
   
### Decoding

To enable online decoding, the argument `--use_streaming true` should be added to `run.sh`.

```sh
./run.sh --stage 12 --use_streaming true
```

### FAQ
1. Issue about `'NoneType' object has no attribute 'max'` during training: Please make sure you employ `forward_train` function during traininig, check more details [here](https://github.com/espnet/espnet/issues/3803).
3. I successfully trained the model, but encountered the above issue during decoding: You may forget to specify `--use_streaming true` to select streaming inference.

## Transducer ASR

ESPnet2 supports models trained with the (RNN-)Tranducer loss, aka Transducer models. This kind of model is defined independently from the other ASR models. For that, we rely on `ESPnetASRTransducerModel` instead of `ESPnetASRModel` and a new task called `ASRTransducerTask` is used in place of `ASRTask`.

**Note:** For the user, it means two things. One, some features or modules may not be supported depending on the model used. Second, the usage of some common ASR features or modules may differ between the models. In addition, some core modules (e.g.: `preencoder` or `postencoder`) or features (e.g.: streaming) were intentionally removed until further testing, specifically for the Transducer model.

### General usage

To enable Transducer model training or decoding in your experiments, the following option should be supplied to `asr.sh` in your `run.sh`:

```sh
asr.sh --asr-transducer true [...]
```

For Transducer loss computation during training, we rely on a fork of `warp-transducer`. The installation procedure is described [here](https://espnet.github.io/espnet/installation.html#step-3-optional-custom-tool-installation).

### Architecture

The architecture is composed of three modules: encoder, decoder and joint network. Each one has a set of up to two parameters settable in order to configure the internal parts. The following sections describe the mandatory and optional parameters for each module.

#### Encoder

For the encoder, we propose an unique encoder type encapsulating the following blocks: Conformer, Conv 1D and RNN. It is similar to the custom encoder in ESPnet1 with the exception that we also support RNN, meaning we don't need to set the parameter `encoder: [type]` here. Instead, the encoder architecture is defined by three parameters passed to `encoder_conf`:

  1. `input_conf (Dict): The configuration for the input block.
  2. `main_conf` (Dict): The main configuration containing the set of high-level parameters used by the whole architecture (i.e.: shared configuration across all blocks). Right now, only Conformer-related parameters are available.
  3. `body_conf` (List[Dict]): The list of configurations for each block of the encoder architecture but the input block.

The first and second configuration are optional and the following parameters can be set:

    main_conf:
      pos_wise_layer_type: Position-wise layer type. (str, default = "linear")
      pos_enc_layer_type: Positional encoding layer type. (str, default = "abs_pos")
      pos_wise_act_type: Position-wise activation type. (str, default = "swish")
      conv_mod_act_type: Convolutional module activation type. (str, default = "swish")

    input_conf:
      block_type: Input block type, either "conv2d" or "vgg". (str, default = "conv2d")
      dim_conv (conv2d only): Convolution output dimension. (int, default = 256)
      subsampling_factor (conv2d only): Subsampling factor of the input block, either 2, 4 or 6. (int, default = 4)
      dropout_rate_pos_enc: Dropout rate for the positional encoding layer, if used. (float, default = 0.0)

The only mandatory parameter is `body_conf`, where a list of configurations for each block of the encoder body architecture need to be given. Each block has its own set of mandatory and optional parameters depending on the type:

    # Conv 1D
    - block_type: conv1d
      dim_output: Output dimension. (int)
      kernel_size: Size of the context window. (int or Tuple)
      stride (optional): Stride of the sliding blocks. (int or tuple, default = 1)
      dilation (optional): Parameter to control the stride of elements within the neighborhood. (int or tuple, default = 1)
      groups (optional): Number of blocked connections from input channels to output channels. (int, default = 1)
      bias (optional): Whether to add a learnable bias to the output. (bool, default = True)
      use_relu (optional): Whether to use a ReLU activation after convolution. (bool, default = True)
      use_batchnorm: Whether to use batch normalization after convolution. (bool, default = False)
      dropout_rate (optional): Dropout rate for the Conv1d outputs. (float, default = 0.0)

    # RNN
    - block_type: rnn
      dim_hidden: Hidden dimension. (int)
      dim_proj (optional): Projection dimension, where 0 means no projection layers. (int, default = 0)
      rnn_type (optional): Type of RNN units (str, default = "lstm")
      bidirectional (optional): Whether bidirectional layers shuld be used. (bool, default = True)
      subsample (optional) Subsampling for each layer when projection layers are used. (sequence, default = (1, 1, 1, 1))
      dropout_rate (optional): Dropout rate for the RNN outputs. (float, default = 0.0)

    # Conformer
    - block_type: conformer
      dim_hidden: Hidden (and output) dimension. (int)
      dim_linear: Dimension of feed-forward module. (int)
      heads (optional): Number of heads in multi-head attention. (int, default = 4)
      macaron_style (optional): Whether to use macaron style. (bool, default = False)
      conv_mod_kernel (optional): Number of kernel in convolutional module, where 0 means no conv. module. (int, default = 0)
      dropout_rate (optional): Dropout rate for some intermediate layers. (float, default = 0.0)]
      dropout_rate_att (optional: Dropout rate for the attention module. (float, default = 0.0)]
      dropout_rate_pos_wise (optional): Dropout rate for the position-wise module. (float, default = 0.0)

Additionally, each block has a parameter `num_blocks` to build N times the defined block. This is useful if you want to build a group of blocks sharing the same parameters without writing each configuration.

**Example 1: conv 2D + 2x Conv 1D + 14x Conformer.**

```yaml
encoder_conf:
    main_conf:
      pos_wise_layer_type: linear
      pos_wise_act_type: swish
      pos_enc_layer_type: rel_pos
      conv_mod_act_type: swish
    input_conf:
      block_type: conv2d
      dim_conv: 256
      subsampling_factor: 4
      dropout_rate_pos_enc: 0.1
    body_conf:
    - block_type: conv1d
      dim_output: 128
      kernel_size: 3
    - block_type: conv1d
      dim_output: 256
      kernel_size: 2
    - block_type: conformer
      dim_linear: 1024
      dim_hidden: 256
      heads: 8
      dropout_rate: 0.1
      dropout_rate_pos_wise: 0.1
      dropout_rate_att: 0.1
      macaron_style: true
      conv_mod_kernel: 31
      num_blocks: 14
```

**Example 2: VGG + 4x RNN w/ projection layers.**

```yaml
encoder_conf:
    input_conf:
      block_type: vgg
    body_conf:
    - block_type: rnn
      num_blocks: 4
      dim_hidden: 512
      dim_proj: 256
```

#### Decoder

For the decoder, two types of blocks are available: RNN and stateless (only embedding). It is defined through two parameters: `decoder` and `decoder_conf`. The first one take a string defining the type of block (either `rnn` or `stateless`) to use while the second takes a single configuration. The following parameters can be set but are all optional:

    decoder_conf:
      rnn_type (RNN only): Type of RNN cells (int, default = "lstm").
      dim_hidden (RNN only): Dimension of the hidden layers (int, default = 256).
      dim_embedding: Dimension of the embedding layer (int, default = 256).
      dropout: Dropout rate for the RNN output nodes (float, default = 0.0).
      dropout_embed: Dropout rate for the embedding layer (float, default = 0.0).

#### Joint network

Currently, we only propose the standard joint network module composed of two three linear layers and an activation functions. The module definition is optional but the following parameters can be modified through the configuration parameter `joint_network_conf`:

    joint_network_conf:
      dim_joint_space: Dimension of the joint space (int, default = 256).
      joint_act_type: Type of activation in the joint network (str, default = "tanh").

### Multi-task learning

We also support multi-task learning with two auxiliary tasks: CTC and cross-entropy w/ label smoothing option (called LM loss here). The auxiliary tasks contributes to the overal task defined as:

L_tot = (λ_trans * L_trans) + (λ_auxCTC * L_auxCTC) + (λ_auxLM + L_auxLM)

where the losses (L_*) are respectively, in order: The Transducer loss, the CTC loss and the LM loss. Lambda values define their respective contribution. Each auxiliary task can be defined through the following parameters passed to `model_conf`:

    model_conf:
      transducer-loss-weight: Weight of the Transducer loss (float, default = 1.0)
      auxiliary_ctc_weight: Weight of the CTC loss. (float, default = 0.0)
      auxiliary_ctc_dropout_rate: Dropout rate for the CTC loss inputs. (float, default = 0.0)
      auxiliary_lm_loss_weight: Weight of the LM loss. (float, default = 0.2)
      auxiliary_lm_loss_smoothing: Smoothing rate for LM loss. If > 0, label smoothing is enabled. (float, default = 0.0)

**Note:** We do not support other auxiliary tasks in ESPnet2 yet.

### Inference

Various decoding algorithms are also available for Transducer by setting `search-type` parameter in your decode config:

  - Beam search algorithm without prefix search [[Graves, 2012]](https://arxiv.org/pdf/1211.3711.pdf). (`search-type: default`)
  - Time Synchronous Decoding [[Saon et al., 2020]](https://ieeexplore.ieee.org/abstract/document/9053040). (`search-type: tsd`)
  - Alignment-Length Synchronous Decoding [[Saon et al., 2020]](https://ieeexplore.ieee.org/abstract/document/9053040). (`search-type: alsd`)
  - modified Adaptive Expansion Search, based on [[Kim et al., 2021]](https://ieeexplore.ieee.org/abstract/document/9250505) and [[Boyer et al., 2021]](https://arxiv.org/pdf/2201.05420.pdf). (`search-type: maes`)

The algorithms share two parameters to control the beam size (`beam-size`) and the final hypotheses normalization (`score-norm`). In addition, three algorithms have specific parameters:

    # Time-synchronous decoding
    search_type: tsd
    max_sym_exp : Number of maximum symbol expansions at each time step. (int > 1, default = 3)

    # Alignement-length decoding
    search_type: alsd
    u_max: Maximum expected target sequence length. (int, default = 50)

    # modified Adaptive Expansion Search
    search_type: maes
    nstep: Number of maximum expansion steps at each time step (int, default = 2)
    expansion_gamma: Number of additional candidates in expanded hypotheses selection. (int, default = 2)
    expansion_beta: Allowed logp difference for prune-by-value method. (float, default = 2.3)

Except for the default algorithm, the described parameters are used to control the performance and decoding speed. The optimal values for each parameter are task-dependent; a high value will typically increase decoding time to focus on performance while a low value will improve decoding time at the expense of performance.