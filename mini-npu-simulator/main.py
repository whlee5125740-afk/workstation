"""Mini NPU console simulator. Python 3.8+, standard library only."""
import argparse
import json
import math
import re
import time
from pathlib import Path

EPSILON = 1e-9


def matrix(value, n):
    if not isinstance(value, list) or len(value) != n:
        raise ValueError('행 개수는 {}이어야 합니다'.format(n))
    result = []
    for row in value:
        if not isinstance(row, list) or len(row) != n:
            raise ValueError('각 행의 열 개수는 {}이어야 합니다'.format(n))
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) for x in row):
            raise ValueError('행렬에는 숫자만 허용합니다')
        try:
            values = [float(x) for x in row]
        except (OverflowError, ValueError):
            raise ValueError('표현 가능한 유한 숫자가 필요합니다')
        if not all(math.isfinite(x) for x in values):
            raise ValueError('NaN/Infinity는 허용하지 않습니다')
        result.append(values)
    return result


def normalize(label):
    if not isinstance(label, str):
        raise ValueError('라벨은 문자열이어야 합니다')
    labels = {'+': 'Cross', 'cross': 'Cross', 'x': 'X'}
    try:
        return labels[label.strip().lower()]
    except KeyError:
        raise ValueError('알 수 없는 라벨: {}'.format(label))


def mac(pattern, kernel):
    """Validated square matrices: one multiplication and accumulation per cell."""
    score = 0.0
    for i in range(len(pattern)):
        for j in range(len(pattern)):
            score += pattern[i][j] * kernel[i][j]
    if not math.isfinite(score):
        raise ValueError('MAC 결과가 유한 범위를 벗어났습니다')
    return score


def mac_flat(pattern, kernel):
    score = 0.0
    for i in range(len(pattern)):
        score += pattern[i] * kernel[i]
    if not math.isfinite(score):
        raise ValueError('MAC 결과가 유한 범위를 벗어났습니다')
    return score


def decide(a, b, labels=('Cross', 'X')):
    if abs(a - b) < EPSILON:
        return 'UNDECIDED'
    return labels[0] if a > b else labels[1]


def generate(n):
    if n < 3 or n % 2 == 0:
        raise ValueError('크기는 3 이상의 홀수여야 합니다')
    cross = [[float(i == n // 2 or j == n // 2) for j in range(n)] for i in range(n)]
    x = [[float(i == j or i + j == n - 1) for j in range(n)] for i in range(n)]
    return cross, x


def benchmark(sizes, repeats=100, pairs=None):
    if repeats < 10:
        raise ValueError('최소 10회 반복해야 합니다')
    print('\n성능 분석: 단일 MAC 호출 평균 / {}회 (I/O·검증·평탄화 제외)'.format(repeats))
    print('크기       평균 시간(ms)    연산 횟수(N²)    1차원(ms)')
    rows = []
    for n in sizes:
        p, k = pairs[n] if pairs and n in pairs else generate(n)
        fp = [v for row in p for v in row]
        fk = [v for row in k for v in row]
        if mac(p, k) != mac_flat(fp, fk):
            raise ValueError('최적화 전후 결과 불일치')
        timings = []
        for fn, a, b in ((mac, p, k), (mac_flat, fp, fk)):
            fn(a, b)
            start = time.perf_counter_ns()
            for _ in range(repeats):
                fn(a, b)
            timings.append((time.perf_counter_ns() - start) / repeats / 1e6)
        print('{:<9} {:>12.6f} {:>16} {:>13.6f}'.format('{}x{}'.format(n, n), timings[0], n*n, timings[1]))
        rows.append((n, timings[0], n*n, timings[1]))
    return rows


def analyze(document):
    if not isinstance(document, dict):
        raise ValueError('최상위 JSON은 객체여야 합니다')
    filters, patterns = document.get('filters'), document.get('patterns')
    if not isinstance(filters, dict) or not isinstance(patterns, dict):
        raise ValueError('filters와 patterns 객체가 필요합니다')
    print('\n필터 로드')
    loaded = {}
    for key, raw in filters.items():
        try:
            match = re.fullmatch(r'size_([1-9][0-9]*)', key)
            if not match or not isinstance(raw, dict):
                raise ValueError('필터 키/객체 스키마 오류')
            n = int(match.group(1))
            normalized = {}
            for label, values in raw.items():
                standard = normalize(label)
                if standard in normalized:
                    raise ValueError('중복 표준 라벨')
                normalized[standard] = matrix(values, n)
            if set(normalized) != {'Cross', 'X'}:
                raise ValueError('Cross, X 필터가 모두 필요합니다')
            loaded[n] = normalized
            print('{}: Cross, X 로드 완료'.format(key))
        except (ValueError, TypeError) as exc:
            print('{}: 필터 오류: {}'.format(key, exc))
    results = []
    print('\n패턴 분석')
    for key, case in patterns.items():
        try:
            match = re.fullmatch(r'size_([1-9][0-9]*)_([0-9]+)', key)
            if not match or not isinstance(case, dict):
                raise ValueError('패턴 키/객체 스키마 오류')
            n = int(match.group(1))
            if n not in loaded:
                raise ValueError('해당 크기의 유효한 필터가 없습니다')
            p = matrix(case.get('input'), n)
            expected = normalize(case.get('expected'))
            start = time.perf_counter_ns()
            a, b = mac(p, loaded[n]['Cross']), mac(p, loaded[n]['X'])
            elapsed = (time.perf_counter_ns() - start) / 1e6
            actual = decide(a, b)
            ok = actual == expected
            reason = '' if ok else ('동점 규칙' if actual == 'UNDECIDED' else 'expected와 판정 불일치')
            print('{} | Cross={:.17g} X={:.17g} | {:.6f} ms | 판정={} expected={} | {} {}'.format(key, a, b, elapsed, actual, expected, 'PASS' if ok else 'FAIL', reason))
        except (ValueError, TypeError) as exc:
            ok, reason = False, str(exc)
            print('{} | FAIL | {}'.format(key, reason))
        results.append((key, ok, reason))
    return results


def summary(results):
    passed = sum(ok for _, ok, _ in results)
    print('\n결과 요약: 총 {} / 통과 {} / 실패 {}'.format(len(results), passed, len(results)-passed))
    for key, ok, reason in results:
        if not ok:
            print('- {}: {}'.format(key, reason))


def read_matrix(title, n=3):
    print('\n{} ({}행, 각 행 {}개 숫자, 공백 구분)'.format(title, n, n))
    rows = []
    while len(rows) < n:
        try:
            raw = input('{}행: '.format(len(rows)+1)).split()
            if len(raw) != n:
                raise ValueError('열 개수가 맞지 않습니다')
            row = [float(v) for v in raw]
            if not all(math.isfinite(v) for v in row):
                raise ValueError('유한 숫자가 필요합니다')
            rows.append(row)
        except ValueError as exc:
            print('입력 오류: {}. 해당 행을 다시 입력하세요.'.format(exc))
    print('{} 저장 완료 ({}x{})'.format(title, n, n))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['1', '2'])
    parser.add_argument('--data', type=Path, default=Path(__file__).with_name('data.json'))
    parser.add_argument('--repeats', type=int, default=100)
    parser.add_argument('--generate', type=int, metavar='N', help='홀수 N의 Cross/X 출력')
    args = parser.parse_args()
    if args.repeats < 10:
        parser.error('--repeats는 10 이상이어야 합니다')
    try:
        if args.generate is not None:
            a, b = generate(args.generate)
            print(json.dumps({'cross': a, 'x': b}, indent=2))
            return 0
        print('=== Mini NPU Simulator ===')
        mode = args.mode
        while mode not in ('1', '2'):
            mode = input('1. 사용자 입력 (3x3)\n2. data.json 분석\n선택: ').strip()
        if mode == '1':
            a = read_matrix('필터 A')
            b = read_matrix('필터 B')
            p = read_matrix('패턴')
            start = time.perf_counter_ns()
            sa, sb = mac(p, a), mac(p, b)
            elapsed = (time.perf_counter_ns() - start) / 1e6
            print('\nA 점수: {:.17g}\nB 점수: {:.17g}\n연산 시간(두 MAC): {:.6f} ms\n판정: {}'.format(sa, sb, elapsed, decide(sa, sb, ('A', 'B'))))
            benchmark([3], args.repeats, {3: (p, a)})
        else:
            with args.data.open(encoding='utf-8-sig') as stream:
                document = json.load(stream)
            results = analyze(document)
            benchmark([3, 5, 13, 25], args.repeats)
            summary(results)
        return 0
    except (OSError, ValueError) as exc:
        print('오류: {}'.format(exc))
        return 2
    except (EOFError, KeyboardInterrupt):
        print('\n입력이 종료되었습니다.')
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
