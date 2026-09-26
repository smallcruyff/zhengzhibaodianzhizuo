"""只解析不执行：把 argparse.ArgumentParser.parse_args 打补丁成“解析成功就打印 PARSED 并退出 0”，再 runpy 执行目标脚本。
用法：python3 argparse_harness.py <script.py> args..."""
import argparse, runpy, sys
sys.dont_write_bytecode = True
_orig = argparse.ArgumentParser.parse_args
def _p(self, args=None, namespace=None):
    ns = _orig(self, args, namespace)
    print('PARSED', {k: v for k, v in vars(ns).items() if k not in ('func', 'f')})
    sys.exit(0)
argparse.ArgumentParser.parse_args = _p
script = sys.argv[1]
sys.argv = [script] + sys.argv[2:]
runpy.run_path(script, run_name='__main__')
