import sys
from os.path import dirname, abspath, join

root_dir = dirname(dirname(abspath(__file__)))
src_dir = join(root_dir, "src")
sys.path.append(src_dir)
