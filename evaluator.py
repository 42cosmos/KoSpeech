"""
    -*- coding: utf-8 -*-

    @source_code{
      title={Character-unit based End-to-End Korean Speech Recognition},
      author={Soohwan Kim, Seyoung Bae, Cheolhwang Won},
      link={https://github.com/sooftware/End-to-End-Korean-Speech-Recognition},
      year={2020}
    }
"""

import queue
import torch
from data_loader import SpectrogramDataset, AudioDataLoader, load_data_list
from definition import logger, id2char, EOS_token, SOS_token
from label_loader import load_targets
from utils import get_distance


class Evaluator:
    """
    Class to evaluate models with given datasets.

    Args: model, batch_size, device
        model (las.las): model to evaluate performance
        batch_size (int): size of batch. recommended batch size is 1.
        device (torch.device): device - 'cuda' or 'cpu'
    """

    def __init__(self, model, batch_size=1, device=None):
        self.model = model
        self.batch_size = batch_size
        self.device = device

    def evaluate(self, args, data_list_path, dataset_path):
        audio_paths, label_paths = load_data_list(data_list_path, dataset_path)
        target_dict = load_targets(label_paths)

        testset = SpectrogramDataset(
            audio_paths=audio_paths,
            label_paths=label_paths,
            sos_id=SOS_token,
            eos_id=EOS_token,
            target_dict=target_dict,
            args=args,
            use_augment=False
        )

        eval_queue = queue.Queue(args.num_workers << 1)
        eval_loader = AudioDataLoader(testset, eval_queue, self.batch_size, 0)
        eval_loader.start()

        cer = self.predict(args, eval_queue)
        logger.info('Evaluate CER : %s' % cer)
        eval_loader.join()

    def predict(self, args, queue):
        logger.info('evaluate() start')
        total_dist = 0
        total_length = 0
        total_sent_num = 0
        time_step = 0

        self.model.eval()

        with torch.no_grad():
            while True:
                inputs, targets, input_lengths, target_lengths = queue.get()
                if inputs.shape[0] == 0:
                    break
                inputs = inputs.to(self.device)
                targets = targets.to(self.device)
                scripts = targets[:, 1:]

                output = self.model(inputs, input_lengths, teacher_forcing_ratio=0.0)

                logit = torch.stack(output, dim=1).to(self.device)
                hypothesis = logit.max(-1)[1]

                dist, length = get_distance(scripts, hypothesis, id2char, EOS_token)
                total_dist += dist
                total_length += length
                total_sent_num += scripts.size(0)

                if time_step % args.print_every == 0:
                    logger.info('cer: {:.2f}'.format(dist / length))

                time_step += 1

        logger.info('evaluate() completed')
        return total_dist / total_length