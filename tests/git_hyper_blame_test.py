#!/usr/bin/env python
# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for git_dates."""

import datetime
import os
import shutil
import StringIO
import sys
import tempfile
import unittest

DEPOT_TOOLS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DEPOT_TOOLS_ROOT)

from testing_support import coverage_utils
from testing_support import git_test_utils

import git_common


class GitHyperBlameTestBase(git_test_utils.GitRepoReadOnlyTestBase):
  @classmethod
  def setUpClass(cls):
    super(GitHyperBlameTestBase, cls).setUpClass()
    import git_hyper_blame
    cls.git_hyper_blame = git_hyper_blame

  def run_hyperblame(self, ignored, filename, revision):
    stdout = StringIO.StringIO()
    stderr = StringIO.StringIO()
    ignored = [self.repo[c] for c in ignored]
    retval = self.repo.run(self.git_hyper_blame.hyper_blame, ignored, filename,
                           revision=revision, out=stdout, err=stderr)
    return retval, stdout.getvalue().rstrip().split('\n')

  def blame_line(self, commit_name, rest, filename=None):
    """Generate a blame line from a commit.

    Args:
      commit_name: The commit's schema name.
      rest: The blame line after the timestamp. e.g., '2) file2 - merged'.
    """
    short = self.repo[commit_name][:8]
    start = '%s %s' % (short, filename) if filename else short
    author = self.repo.show_commit(commit_name, format_string='%an %ai')
    return '%s (%s %s' % (start, author, rest)

class GitHyperBlameMainTest(GitHyperBlameTestBase):
  """End-to-end tests on a very simple repo."""
  REPO_SCHEMA = "A B C"

  COMMIT_A = {
    'some/files/file': {'data': 'line 1\nline 2\n'},
  }

  COMMIT_B = {
    'some/files/file': {'data': 'line 1\nline 2.1\n'},
  }

  COMMIT_C = {
    'some/files/file': {'data': 'line 1.1\nline 2.1\n'},
  }

  def testBasicBlame(self):
    """Tests the main function (simple end-to-end test with no ignores)."""
    expected_output = [self.blame_line('C', '1) line 1.1'),
                       self.blame_line('B', '2) line 2.1')]
    stdout = StringIO.StringIO()
    stderr = StringIO.StringIO()
    retval = self.repo.run(self.git_hyper_blame.main,
                           args=['tag_C', 'some/files/file'], stdout=stdout,
                           stderr=stderr)
    self.assertEqual(0, retval)
    self.assertEqual(expected_output, stdout.getvalue().rstrip().split('\n'))
    self.assertEqual('', stderr.getvalue())

  def testIgnoreSimple(self):
    """Tests the main function (simple end-to-end test with ignores)."""
    expected_output = [self.blame_line('C', ' 1) line 1.1'),
                       self.blame_line('A', '2*) line 2.1')]
    stdout = StringIO.StringIO()
    stderr = StringIO.StringIO()
    retval = self.repo.run(self.git_hyper_blame.main,
                           args=['-i', 'tag_B', 'tag_C', 'some/files/file'],
                           stdout=stdout, stderr=stderr)
    self.assertEqual(0, retval)
    self.assertEqual(expected_output, stdout.getvalue().rstrip().split('\n'))
    self.assertEqual('', stderr.getvalue())

  def testBadRepo(self):
    """Tests the main function (not in a repo)."""
    # Make a temp dir that has no .git directory.
    curdir = os.getcwd()
    tempdir = tempfile.mkdtemp(suffix='_nogit', prefix='git_repo')
    try:
      os.chdir(tempdir)
      stdout = StringIO.StringIO()
      stderr = StringIO.StringIO()
      retval = self.git_hyper_blame.main(
          args=['-i', 'tag_B', 'tag_C', 'some/files/file'], stdout=stdout,
          stderr=stderr)
    finally:
      shutil.rmtree(tempdir)
      os.chdir(curdir)

    self.assertNotEqual(0, retval)
    self.assertEqual('', stdout.getvalue())
    self.assertRegexpMatches(stderr.getvalue(), '^fatal: Not a git repository')

  def testBadFilename(self):
    """Tests the main function (bad filename)."""
    stdout = StringIO.StringIO()
    stderr = StringIO.StringIO()
    retval = self.repo.run(self.git_hyper_blame.main,
                           args=['-i', 'tag_B', 'tag_C', 'some/files/xxxx'],
                           stdout=stdout, stderr=stderr)
    self.assertNotEqual(0, retval)
    self.assertEqual('', stdout.getvalue())
    self.assertEqual('fatal: no such path some/files/xxxx in %s\n' %
                     self.repo['C'], stderr.getvalue())

  def testBadRevision(self):
    """Tests the main function (bad revision to blame from)."""
    stdout = StringIO.StringIO()
    stderr = StringIO.StringIO()
    retval = self.repo.run(self.git_hyper_blame.main,
                           args=['-i', 'tag_B', 'xxxx', 'some/files/file'],
                           stdout=stdout, stderr=stderr)
    self.assertNotEqual(0, retval)
    self.assertEqual('', stdout.getvalue())
    self.assertRegexpMatches(stderr.getvalue(),
                             '^fatal: ambiguous argument \'xxxx\': unknown '
                             'revision or path not in the working tree.')

  def testBadIgnore(self):
    """Tests the main function (bad revision passed to -i)."""
    stdout = StringIO.StringIO()
    stderr = StringIO.StringIO()
    retval = self.repo.run(self.git_hyper_blame.main,
                           args=['-i', 'xxxx', 'tag_C', 'some/files/file'],
                           stdout=stdout, stderr=stderr)
    self.assertNotEqual(0, retval)
    self.assertEqual('', stdout.getvalue())
    self.assertEqual('fatal: unknown revision \'xxxx\'.\n', stderr.getvalue())

class GitHyperBlameSimpleTest(GitHyperBlameTestBase):
  REPO_SCHEMA = """
  A B D E F G H
  A C D
  """

  COMMIT_A = {
    'some/files/file1': {'data': 'file1'},
    'some/files/file2': {'data': 'file2'},
    'some/files/empty': {'data': ''},
    'some/other/file':  {'data': 'otherfile'},
  }

  COMMIT_B = {
    'some/files/file2': {
      'mode': 0755,
      'data': 'file2 - vanilla\n'},
    'some/files/empty': {'data': 'not anymore'},
    'some/files/file3': {'data': 'file3'},
  }

  COMMIT_C = {
    'some/files/file2': {'data': 'file2 - merged\n'},
  }

  COMMIT_D = {
    'some/files/file2': {'data': 'file2 - vanilla\nfile2 - merged\n'},
  }

  COMMIT_E = {
    'some/files/file2': {'data': 'file2 - vanilla\nfile_x - merged\n'},
  }

  COMMIT_F = {
    'some/files/file2': {'data': 'file2 - vanilla\nfile_y - merged\n'},
  }

  # Move file2 from files to other.
  COMMIT_G = {
    'some/files/file2': {'data': None},
    'some/other/file2': {'data': 'file2 - vanilla\nfile_y - merged\n'},
  }

  COMMIT_H = {
    'some/other/file2': {'data': 'file2 - vanilla\nfile_z - merged\n'},
  }

  def testBlameError(self):
    """Tests a blame on a non-existent file."""
    expected_output = ['']
    retval, output = self.run_hyperblame([], 'some/other/file2', 'tag_D')
    self.assertNotEqual(0, retval)
    self.assertEqual(expected_output, output)

  def testBlameEmpty(self):
    """Tests a blame of an empty file with no ignores."""
    expected_output = ['']
    retval, output = self.run_hyperblame([], 'some/files/empty', 'tag_A')
    self.assertEqual(0, retval)
    self.assertEqual(expected_output, output)

  def testBasicBlame(self):
    """Tests a basic blame with no ignores."""
    # Expect to blame line 1 on B, line 2 on C.
    expected_output = [self.blame_line('B', '1) file2 - vanilla'),
                       self.blame_line('C', '2) file2 - merged')]
    retval, output = self.run_hyperblame([], 'some/files/file2', 'tag_D')
    self.assertEqual(0, retval)
    self.assertEqual(expected_output, output)

  def testBlameRenamed(self):
    """Tests a blame with no ignores on a renamed file."""
    # Expect to blame line 1 on B, line 2 on H.
    # Because the file has a different name than it had when (some of) these
    # lines were changed, expect the filenames to be displayed.
    expected_output = [self.blame_line('B', '1) file2 - vanilla',
                                       filename='some/files/file2'),
                       self.blame_line('H', '2) file_z - merged',
                                       filename='some/other/file2')]
    retval, output = self.run_hyperblame([], 'some/other/file2', 'tag_H')
    self.assertEqual(0, retval)
    self.assertEqual(expected_output, output)

  def testIgnoreSimpleEdits(self):
    """Tests a blame with simple (line-level changes) commits ignored."""
    # Expect to blame line 1 on B, line 2 on E.
    expected_output = [self.blame_line('B', '1) file2 - vanilla'),
                       self.blame_line('E', '2) file_x - merged')]
    retval, output = self.run_hyperblame([], 'some/files/file2', 'tag_E')
    self.assertEqual(0, retval)
    self.assertEqual(expected_output, output)

    # Ignore E; blame line 1 on B, line 2 on C.
    expected_output = [self.blame_line('B', ' 1) file2 - vanilla'),
                       self.blame_line('C', '2*) file_x - merged')]
    retval, output = self.run_hyperblame(['E'], 'some/files/file2', 'tag_E')
    self.assertEqual(0, retval)
    self.assertEqual(expected_output, output)

    # Ignore E and F; blame line 1 on B, line 2 on C.
    expected_output = [self.blame_line('B', ' 1) file2 - vanilla'),
                       self.blame_line('C', '2*) file_y - merged')]
    retval, output = self.run_hyperblame(['E', 'F'], 'some/files/file2',
                                         'tag_F')
    self.assertEqual(0, retval)
    self.assertEqual(expected_output, output)

  def testIgnoreInitialCommit(self):
    """Tests a blame with the initial commit ignored."""
    # Ignore A. Expect A to get blamed anyway.
    expected_output = [self.blame_line('A', '1) file1')]
    retval, output = self.run_hyperblame(['A'], 'some/files/file1', 'tag_A')
    self.assertEqual(0, retval)
    self.assertEqual(expected_output, output)

  def testIgnoreFileAdd(self):
    """Tests a blame ignoring the commit that added this file."""
    # Ignore A. Expect A to get blamed anyway.
    expected_output = [self.blame_line('B', '1) file3')]
    retval, output = self.run_hyperblame(['B'], 'some/files/file3', 'tag_B')
    self.assertEqual(0, retval)
    self.assertEqual(expected_output, output)

  def testIgnoreFilePopulate(self):
    """Tests a blame ignoring the commit that added data to an empty file."""
    # Ignore A. Expect A to get blamed anyway.
    expected_output = [self.blame_line('B', '1) not anymore')]
    retval, output = self.run_hyperblame(['B'], 'some/files/empty', 'tag_B')
    self.assertEqual(0, retval)
    self.assertEqual(expected_output, output)

class GitHyperBlameLineMotionTest(GitHyperBlameTestBase):
  REPO_SCHEMA = """
  A B C D E
  """

  COMMIT_A = {
    'file':  {'data': 'A\ngreen\nblue\n'},
  }

  # Change "green" to "yellow".
  COMMIT_B = {
    'file': {'data': 'A\nyellow\nblue\n'},
  }

  # Insert 2 lines at the top,
  # Change "yellow" to "red".
  COMMIT_C = {
    'file': {'data': 'X\nY\nA\nred\nblue\n'},
  }

  # Insert 2 more lines at the top.
  COMMIT_D = {
    'file': {'data': 'earth\nfire\nX\nY\nA\nred\nblue\n'},
  }

  # Insert a line before "red", and indent "red" and "blue".
  COMMIT_E = {
    'file': {'data': 'earth\nfire\nX\nY\nA\ncolors:\n red\n blue\n'},
  }

  def testInterHunkLineMotion(self):
    """Tests a blame with line motion in another hunk in the ignored commit."""
    # This test was mostly written as a demonstration of the limitations of the
    # current algorithm (it exhibits non-ideal behaviour).

    # Blame from D, ignoring C.
    # Lines 1, 2 were added by D.
    # Lines 3, 4 were added by C (but ignored, so blame A, B, respectively).
    # TODO(mgiuca): Ideally, this would blame both of these lines on A, because
    # they add lines nowhere near the changes made by B.
    # Line 5 was added by A.
    # Line 6 was modified by C (but ignored, so blame A).
    # TODO(mgiuca): Ideally, Line 6 would be blamed on B, because that was the
    # last commit to touch that line (changing "green" to "yellow"), but the
    # algorithm isn't yet able to figure out that Line 6 in D == Line 4 in C ~=
    # Line 2 in B.
    # Line 7 was added by A.
    expected_output = [self.blame_line('D', ' 1) earth'),
                       self.blame_line('D', ' 2) fire'),
                       self.blame_line('A', '3*) X'),
                       self.blame_line('B', '4*) Y'),
                       self.blame_line('A', ' 5) A'),
                       self.blame_line('A', '6*) red'),
                       self.blame_line('A', ' 7) blue'),
                       ]
    retval, output = self.run_hyperblame(['C'], 'file', 'tag_D')
    self.assertEqual(0, retval)
    self.assertEqual(expected_output, output)

  def testIntraHunkLineMotion(self):
    """Tests a blame with line motion in the same hunk in the ignored commit."""
    # This test was mostly written as a demonstration of the limitations of the
    # current algorithm (it exhibits non-ideal behaviour).

    # Blame from E, ignoring E.
    # Line 6 was added by E (but ignored, so blame C).
    # Lines 7, 8 were modified by E (but ignored, so blame A).
    # TODO(mgiuca): Ideally, this would blame Line 7 on C, because the line
    # "red" was added by C, and this is just a small change to that line. But
    # the current algorithm can't deal with line motion within a hunk, so it
    # just assumes Line 7 in E ~= Line 7 in D == Line 3 in A (which was "blue").
    expected_output = [self.blame_line('D', ' 1) earth'),
                       self.blame_line('D', ' 2) fire'),
                       self.blame_line('C', ' 3) X'),
                       self.blame_line('C', ' 4) Y'),
                       self.blame_line('A', ' 5) A'),
                       self.blame_line('C', '6*) colors:'),
                       self.blame_line('A', '7*)  red'),
                       self.blame_line('A', '8*)  blue'),
                       ]
    retval, output = self.run_hyperblame(['E'], 'file', 'tag_E')
    self.assertEqual(0, retval)
    self.assertEqual(expected_output, output)


if __name__ == '__main__':
  sys.exit(coverage_utils.covered_main(
    os.path.join(DEPOT_TOOLS_ROOT, 'git_hyper_blame.py')))