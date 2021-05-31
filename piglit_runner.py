#!/usr/bin/python3
from subprocess import call, check_output, CalledProcessError
from os.path import exists, join, abspath, realpath, split as splitpath, isdir
import json
import re
import os

BASE_PATH = abspath(splitpath(realpath(__file__))[0])
GL_VERSIONS = [10, 11, 12, 20, 21, 30, 31, 32, 33, 40, 41, 42, 43, 44, 45, 46]
GLSL_VERSIONS = [110, 120, 130, 140, 150,
                 330, 400, 410, 420, 430, 440, 450, 460]

gl_pattern = re.compile('opengl version string:\s*(\d)\s*\.\s*(\d)',
                        flags=re.IGNORECASE)
glsl_pattern = re.compile(
    'opengl shading language version string:\s*(\d)\s*\.\s*(\d\d)',
    flags=re.IGNORECASE)
ext_pattern = re.compile('opengl extensions:\s*([\w\s]*)', flags=re.IGNORECASE)


def run(log):
    os.environ['PIGLIT_NO_FAST_SKIP'] = '1'
    os.environ['PIGLIT_COMPRESSION'] = 'none'
    os.environ['PIGLIT_FORCE_GLSLPARSER_DESKTOP'] = '1'

    # call wflinfo and get the supported gl version and extensions.
    try:
        context_info = str(check_output(['wflinfo',
                                         '--platform', 'glx',
                                         '--api', 'gl',
                                         '--verbose']))
    except CalledProcessError:
        log.write('Cannot execute wflinfo. Ensure to add it in system path')
        return False

    gl_version = gl_pattern.search(context_info)
    glsl_version = glsl_pattern.search(context_info)
    ext = ext_pattern.search(context_info)

    # build wanted test cases.
    if gl_version is None:
        log.write('No gl version match found')
        return False

    if glsl_version is None:
        log.write('No glsl version match found')
        return False

    if ext is None:
        log.write('No extensions match found')
        return False

    gl_major, gl_minor = map(int, gl_version.groups())
    gl_version = gl_major * 10 + gl_minor
    try:
        index = GL_VERSIONS.index(gl_version)
    except:
        log.write('Detected gl version %d is not allowed' % gl_version)
        return False

    gl_versions = GL_VERSIONS[:index+1]

    glsl_major, glsl_minor = map(int, glsl_version.groups())
    glsl_version = glsl_major * 100 + glsl_minor
    try:
        index = GLSL_VERSIONS.index(glsl_version)
    except:
        log.write('Detected glsl version %d is not allowed' % glsl_version)
        return False

    glsl_versions = GLSL_VERSIONS[:index+1]

    wanted_tests = set(e[3:].lower() for e in ext.groups()[
        0].split(' ') if e.startswith('GL'))
    for v in gl_versions:
        wanted_tests.add('gl-%s.%s' % (str(v)[0], str(v)[1:]))

    for v in glsl_versions:
        wanted_tests.add('glsl-%s.%s' % (str(v)[0], str(v)[1:]))

    # intersection.
    spec_path = join(BASE_PATH, 'tests', 'spec')
    available_tests = (o.lower() for o in os.listdir(
        spec_path) if isdir(join(spec_path, o)))
    tests = wanted_tests.intersection(available_tests)
    # takes too much to complete. Explanation: too many texture readbacks.
    tests.discard('ext_texture_env_combine')

    # generate test case list.
    piglit_command = ['python', 'piglit', 'run',
                      'tests/all', '-o', '-d', '-p', 'glx', '-l', 'quiet', ]
    for t in tests:
        piglit_command.append('-t')
        piglit_command.append(t)

    piglit_command.append('./results/in')
    if call(piglit_command) != 0:
        log.write('Cannot generate cases. Ensure piglit is in system path')
        return False

    # collect all tests.
    cases_file = join(BASE_PATH, 'results', 'in', 'results.json')
    if not exists(cases_file):
        log.write('Error: cannot find cases file %s' % cases_file)
        return False

    try:
        all_tests = set(
            json.load(open(cases_file, 'r')).get('tests').keys())
    except:
        all_tests = set()

    # collect tests to include.
    include_file = join(BASE_PATH, 'include.txt')
    try:
        include_tests = set(
            map(str.strip, open(include_file, 'r').readlines()))
    except:
        include_tests = set()

    caselist = all_tests.intersection(include_tests)
    caselist_file = join(BASE_PATH, 'results', 'run0_in.txt')
    open(caselist_file, 'w').write('\n'.join(sorted(caselist)))

    # execute test case list.
    if call(['python',
             'piglit',
             'run', 'tests/all',
             '-o',
             '-p', 'glx',
             '-l', 'quiet',
             '--process-isolation', 'true',
             './results/run0_out',
             '--test-list', abspath(caselist_file)]) != 0:
        log.write('Cannot run piglit cases. Ensure piglit is in system path')
        return False

    # load results file.
    # all generated tests must be executed (no matter the output).
    result_file = join(BASE_PATH, 'results', 'run0_out', 'results.json')
    if not exists(result_file):
        log.write('Cannot find result file %s' % result_file)
        return False

    try:
        results = json.load(open(result_file, 'r'))
        tests = results.get('tests')
    except:
        tests = None

    if tests is None:
        log.write('Cannot retrieve tests from json file')
        return False

    for case in caselist:
        if case not in tests:
            log.write('Test %s was not executed', case)
            return False

    return True


if __name__ == '__main__':
    log_file = join(BASE_PATH, 'log.txt')
    with open(log_file, 'w') as log:
        if not run(log):
            exit(1)

    exit(0)