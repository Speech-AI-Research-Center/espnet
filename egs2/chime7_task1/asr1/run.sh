#!/usr/bin/env bash
# Set bash to 'debug' mode, it will exit on :
# -e 'error', -u 'undefined variable', -o ... 'error in pipeline', -x 'print commands',
set -euo pipefail
# main stages
stage=1
stop_stage=1

# NOTE, use absolute paths !
chime7_root=${PWD}/chime7_task1
chime5_root= # you can leave it empty if you have already generated CHiME-6 data
chime6_root=/raid/users/popcornell/CHiME6/espnet/egs2/chime6/asr1/CHiME6 # will be created automatically from chime5
# but if you have it already it will be skipped
dipco_root=${PWD}/datasets/dipco # this will be automatically downloaded
mixer6_root=/raid/users/popcornell/mixer6/
manifests_root=./data/lhotse

# dataprep options
cmd_dprep=run.pl
dprep_stage=2
gss_dump_root=./exp/gss
ngpu=6  # set equal to the number of GPUs you have, used for GSS and ASR training

. ./path.sh
. ./cmd.sh
. ./utils/parse_options.sh

# gss config
max_batch_dur=360 # set accordingly to your GPU VRAM, here I used 40GB
cmd_gss=run.pl
gss_dsets=chime6_dev dipco_dev mixer6_dev

# asr config
# NOTE: if you get OOM reduce the batch size in asr_config YAML file
asr_stage=0 # starts at 13 for inference only
bpe_nlsyms=""
asr_config=conf/tuning/train_asr_transformer_wavlm_lr1e-4_specaugm_accum1_preenc128_warmup40k.yaml
inference_config="conf/decode_asr_transformer.yaml"
lm_config="conf/train_lm.yaml"
use_lm=false
use_word_lm=false
word_vocab_size=65000
nbpe=500
max_wav_duration=30

if [ ${stage} -le 0 ] && [ $stop_stage -ge 0 ]; then
  # create the dataset
  local/create_task1_data.sh --chime6-root $chime6_root --stage $dprep_stage  --chime7-root $chime7_root \
	  --dipco-root $dipco_root \
	  --mixer6-root $mixer6_root \
	  --stage $dprep_stage \
	  --train_cmd $cmd_dprep
fi


if [ ${stage} -le 1 ] && [ $stop_stage -ge 1 ]; then
  # parse dset to lhotse
  for dset in chime6 dipco mixer6; do
    for dset_part in train dev; do
      if [ $dset == dipco ] && [ $dset_part == train ]; then
          continue # dipco has no train set
      fi
      echo "Creating lhotse manifests for ${dset} in $manifests_root/${dset}"
      python local/get_lhotse_manifests.py -c $chime7_root \
           -d $dset \
           -p $dset_part \
           -o $manifests_root \
           --ignore_shorter 0.2
    done
  done
fi


if [ ${stage} -le 2 ] && [ $stop_stage -ge 2 ]; then
  # check if GSS is installed, if not stop, user must manually install it
  if [ ! command -v gss &> /dev/null ];
    then
      echo "GPU-based Guided Source Separation (GSS) could not be found,
      please refer to the README for how to install it. \n
      See also https://github.com/desh2608/gss for more informations."
      exit
  fi

  for dset in $gss_dsets; do
    dset_name="$(cut -d'_' -f1 <<<${dset})"
    dset_part="$(cut -d'_' -f2 <<<${dset})"

    max_segment_length=200 # enhance all
    channels=all # do not set for the other datasets, use all
    if [ $dset_name == dipco ] && [ $dset_part == train ]; then
      echo "DiPCo has no training set ! exiting"
      exit
    fi

    if [ $dset_name == dipco ]; then
      channels=2,5,9,12,16,19,23,26,30,33 #dipco only using opposite mics on each array, works better
    fi

    if [ $dset_part == train ]; then
      max_segment_length=$max_wav_duration # we can discard utterances too long based on asr training
    fi
    echo "Running Guided Source Separation for ${dset_name}/${dset_part}, results will be in ${gss_dump_root}/${dset_name}/${dset_part}"
    ./run_gss.sh --manifests-dir $manifests_root --dset-name $dset_name \
          --dset-part $dset_part \
          --exp-dir $gss_dump_root \
          --cmd $cmd_gss \
          --nj $ngpu \
          --max-segment-length $max_segment_length \
          --max-batch-duration $max_batch_dur \
          --channels $channels
    echo "Guided Source Separation processing for ${dset_name}/${dset_part} was successful !"
  done
fi

if [ ${stage} -le 3 ] && [ $stop_stage -ge 3 ]; then
    # Preparing ASR training and validation data;
    echo "Parsing the GSS output to lhotse manifests which will be placed in ${manifests_root}/${dset_name}/${dset_part}"
    for dset_part in dev; do
    for dset_name in mixer6; do
      if [ $dset == dipco ] && [ $dset_part == train ]; then
          continue # dipco has no train set
      fi
      python local/data/gss2lhotse.py -i $gss_dump_root -o $manifests_root/gss/

    # train set
    echo "Dumping all lhotse manifests to kaldi manifests and merging everything for training set."
    tr_kaldi_manifests=()
    dset_part=train
    mic=ihm
    for dset in chime6 mixer6; do
      for mic in ihm mdm gss; do
        if [ $dset == mixer6 ] && [ $mic == ihm ]; then
          continue # not used right now
        fi
      lhotse kaldi export -p ${manifests_root}/${dset}/${dset_part}/${dset}-${mic}_recordings_${dset_part}.jsonl.gz  ${manifests_root}/${dset}/${dset_part}/${dset}-${mic}_supervisions_${dset_part}.jsonl.gz data/kaldi/${dset}/${dset_part}/${mic}
      ./utils/utt2spk_to_spk2utt.pl data/kaldi/${dset}/${dset_part}/${mic}/utt2spk > data/kaldi/${dset}/${dset_part}/${mic}/spk2utt
      ./utils/fix_data_dir.sh data/kaldi/${dset}/${dset_part}/${mic}
      tr_kaldi_manifests+=( "data/kaldi/$dset/$dset_part/$mic" )
      done
    done
    echo ${tr_kaldi_manifests[@]}
    ./utils/combine_data.sh data/kaldi/train_all ${tr_kaldi_manifests[@]}
    ./utils/fix_data_dir.sh data/kaldi/train_all

    # dev set ihm
    echo "Dumping all lhotse manifests to kaldi manifests for dev set with close-talk microphones."
    cv_kaldi_manifests_ihm=()
    dset_part=dev
    mic=ihm
    for dset in chime6 dipco; do
      lhotse kaldi export -p ${manifests_root}/${dset}/${dset_part}/${dset}-${mic}_recordings_${dset_part}.jsonl.gz  ${manifests_root}/${dset}/${dset_part}/${dset}-${mic}_supervisions_${dset_part}.jsonl.gz data/kaldi/${dset}/${dset_part}/${mic}
      ./utils/utt2spk_to_spk2utt.pl data/kaldi/${dset}/${dset_part}/${mic}/utt2spk > data/kaldi/${dset}/${dset_part}/${mic}/spk2utt
      ./utils/fix_data_dir.sh data/kaldi/${dset}/${dset_part}/${mic}
      cv_kaldi_manifests_ihm+=( "data/kaldi/$dset/$dset_part/$mic" )
    done
    echo ${cv_kaldi_manifests_ihm[@]}
    ./utils/combine_data.sh data/kaldi/dev_ihm_all ${cv_kaldi_manifests_ihm[@]}
    ./utils/fix_data_dir.sh data/kaldi/dev_ihm_all

    echo "Dumping all lhotse manifests to kaldi manifests for dev set with GSS enhanced output."
    # dev set gss
    #dset_part=dev
    #mic=gss
    #for dset in chime6 dipco mixer6; do
     # lhotse kaldi export -p $manifests_root/$dset/$dset_part/$dset- data/kaldi/$dset/$dset_part/$mic
     # $cv_kaldi_manifests_gss+=" data/kaldi/$dset/$dset_part/$mic"
    #done
    #./utils/combine_data.sh data/kaldi/dev_gss $cv_kaldi_manifests_gss
fi


if [ ${stage} -le 4 ] && [ $stop_stage -ge 4 ]; then
  asr_train_set=kaldi/train_all
  asr_cv_set=kaldi/dev_gss_all
  # decoding on dev set because test is blind for now
  asr_tt_set="kaldi/chime6/dev_gss kaldi/dipco/dev_gss kaldi/mixer6/dev_gss"
  ./asr.sh \
    --lang en \
    --local_data_opts "--train-set ${asr_train_set}" \
    --stage $asr_stage \
    --ngpu $ngpu \
    --token_type bpe \
    --nbpe $nbpe \
    --bpe_nlsyms "${bpe_nlsyms}" \
    --nlsyms_txt "data/nlsyms.txt" \
    --feats_type raw \
    --feat_normalize utterance_mvn \
    --audio_format "flac" \
    --max_wav_duration $max_wav_duration \
    --speed_perturb_factors "0.9 1.0 1.1" \
    --asr_config "${asr_config}" \
    --inference_config "${inference_config}" \
    --use_lm ${use_lm} \
    --lm_config "${lm_config}" \
    --use_word_lm ${use_word_lm} \
    --word_vocab_size ${word_vocab_size} \
    --train_set "${asr_train_set}" \
    --valid_set "${asr_cv_set}" \
    --test_sets "${asr_tt_set}" \
    --bpe_train_text "data/${asr_train_set}/text" \
    --lm_train_text "data/${asr_train_set}/text" "$@"
fi

if [ ${stage} -le 5 ] && [ $stop_stage -ge 5 ]; then
  # run evaluation


fi