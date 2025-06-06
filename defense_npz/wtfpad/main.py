import sys
import argparse
import configparser
import numpy as np

from os import mkdir
from os.path import join, isdir
import os

from time import strftime

import tqdm

import adaptive as ap
import constants as ct
import overheads as oh
from pparser import Trace, Packet

import logging


logger = logging.getLogger('wtfpad')


def init_directories(config):
    # Create a results dir if it doesn't exist yet
    if not isdir(ct.RESULTS_DIR):
        mkdir(ct.RESULTS_DIR)

    # Define output directory
    timestamp = strftime('%m%d_%H%M')
    output_dir = join(ct.RESULTS_DIR, 'wtfpad' + '_' + timestamp)
    logger.info("Creating output directory: %s" % output_dir)

    # make the output directory
    if not isdir(output_dir):
        mkdir(output_dir)

    return output_dir


def main():
    # parser config and arguments
    args, config = parse_arguments()
    logger.info("Arguments: %s, Config: %s" % (args, config))

    # Init run directories
    output_dir = init_directories(args.section)

    # Instantiate a new adaptive padding object
    wtfpad = ap.AdaptiveSimulator(config)

    # Traverse all traces
    data = np.load(args.traces_path + "/data.npz")
    X = data["X"]
    y = data["y"]

    # Run simulation on all traces
    latencies, bandwidths = [], []
    count = -1
    key_array = np.lib.format.open_memmap("large_data_key.npy", mode="w+", dtype="float32", shape=X.shape)
    for p, label in tqdm.tqdm(zip(X, y)):
        count += 1
        # Parse
        trace = Trace()
        for i in range(len(p)):
            timestamp, length = p[i, 0], p[i, 1]
            if timestamp == 0 and length == 0:
                break

            direction = int(length) // abs(int(length))

            trace.append(Packet(float(timestamp), direction, abs(int(length))))

        logger.info("Simulating trace: %s" % str(count))
        simulated = wtfpad.simulate(Trace(trace))
        # dump simulated trace to results directory

        for i in range(len(simulated)):
            key_array[count, i, 0] = simulated[i].timestamp
            key_array[count, i, 1] = simulated[i].direction * simulated[i].length

            if i == key_array.shape[1] - 1:
                break

        # calculate overheads
        bw_ovhd = oh.bandwidth_ovhd(simulated, trace)
        bandwidths.append(bw_ovhd)
        logger.debug("Bandwidth overhead: %s" % bw_ovhd)

        lat_ovhd = oh.latency_ovhd(simulated, trace)
        latencies.append(lat_ovhd)
        logger.debug("Latency overhead: %s" % lat_ovhd)

    np.savez(os.path.join(output_dir, "data.npz"), X=key_array, y=y)
    os.remove("large_data_key.npy")
    logger.info("Latency overhead: %s" % np.median([l for l in latencies if l > 0.0]))
    logger.info("Bandwidth overhead: %s" % np.median([b for b in bandwidths if b > 0.0]))


def parse_arguments():
    # Read configuration file
    conf_parser = configparser.RawConfigParser()
    conf_parser.read(ct.CONFIG_FILE)

    parser = argparse.ArgumentParser(description='It simulates adaptive padding on a set of web traffic traces.')

    parser.add_argument('--traces_path',
                        metavar='<traces path>',
                        default="../../npz_dataset/Closed_2tab",
                        help='Path to the directory with the traffic traces to be simulated.')

    parser.add_argument('-c', '--config',
                        dest="section",
                        metavar='<config name>',
                        help="Adaptive padding configuration.",
                        choices=conf_parser.sections(),
                        default="normal_rcv")

    parser.add_argument('--log',
                        type=str,
                        dest="log",
                        metavar='<log path>',
                        default='stdout',
                        help='path to the log file. It will print to stdout by default.')

    parser.add_argument('--log-level',
                        type=str,
                        dest="loglevel",
                        metavar='<log level>',
                        help='logging verbosity level.')

    # Parse arguments
    args = parser.parse_args()

    # Get section in config file
    config = conf_parser._sections[args.section]

    # Use default values if not specified
    config = dict(config, **conf_parser._sections['normal_rcv'])

    # logging config
    config_logger(args)

    return args, config


def config_logger(args):
    # Set file
    log_file = sys.stdout
    if args.log != 'stdout':
        log_file = open(args.log, 'w')
    ch = logging.StreamHandler(log_file)

    # Set logging format
    ch.setFormatter(logging.Formatter(ct.LOG_FORMAT))
    logger.addHandler(ch)

    # Set level format
    logger.setLevel(logging.INFO)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(-1)
