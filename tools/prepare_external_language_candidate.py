"""Language preflight or explicitly requested candidate12 manual package; never flash."""
import argparse,json
from review_process_language_cache import review,summary

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--check-only',action='store_true',help='Verify optimized inputs without a package.')
 p.add_argument('--prepare-local-review',action='store_true',help='Build candidate12 manual package; refuse existing outputs; never run updater.')
 args=p.parse_args()
 if args.check_only==args.prepare_local_review:p.error('Choose exactly one of --check-only or --prepare-local-review')
 if args.prepare_local_review:
  from prepare_cached_language_candidate import main as prepare
  prepare()
 else:print(json.dumps(summary(review()),indent=2))
if __name__=='__main__':main()
