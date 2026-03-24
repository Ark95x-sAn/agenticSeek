import argparse
import json
import logging
import sys

from ark95x import __version__, ARK95XConfig, ARK95XOrchestrator


def setup_logging(verbose=False):
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format='[%(asctime)s] %(name)s %(levelname)s: %(message)s',
    )


def main():
    parser = argparse.ArgumentParser(prog='ark95x')
    sub = parser.add_subparsers(dest='command')
    sub.add_parser('run')
    sub.add_parser('status')
    sub.add_parser('version')
    parser.add_argument('--config', type=str, default=None)
    parser.add_argument('--verbose', action='store_true')

    args = parser.parse_args()
    setup_logging(args.verbose)

    try:
        if args.command == 'version':
            print(f'ARK95X v{__version__}')
        elif args.command == 'status':
            orch = ARK95XOrchestrator(ARK95XConfig())
            print(json.dumps(orch.health_check(), indent=2))
        else:
            config = ARK95XConfig()
            if args.config:
                with open(args.config, 'r', encoding='utf-8') as fp:
                    config_data = json.load(fp)
                for key, value in config_data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
            orch = ARK95XOrchestrator(config)
            orch.run()
    except Exception as e:
        print(f'\033[91mError: {e}\033[0m', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
