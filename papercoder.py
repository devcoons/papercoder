import random
import string
from collections import Counter
import argparse
import sys

# ---------------------------------------------------------------------- #
#                             UTILITY FUNCTIONS                          #
# ---------------------------------------------------------------------- #

def generate_noise_token(exclude_set, text_tokens, single_char_probability=0.5):
    """
    Generate a noise token (1 or 2 chars), not in exclude_set or text_tokens.
    """
    exclude_set = set(exclude_set)
    text_tokens = set(text_tokens)
    charset = string.ascii_letters + string.digits
    while True:
        token = ''.join(random.choices(charset, k=2))
        if (token not in exclude_set and
            token[::-1] not in exclude_set and
            token not in text_tokens):
            return token

# ---------------------------------------------------------------------- #

def get_text_tokens(text):
    """
    Split text into 2-character tokens.
    """
    return [text[i:i+2] for i in range(0, len(text), 2)]

# ---------------------------------------------------------------------- #

def get_password_tokens(password):
    """
    Get all valid password 2-char tokens, skipping:
    - tokens where both chars are the same
    - tokens whose reverse also exists in the list
    - any repeated tokens (if a token appears more than once, it's excluded entirely)
    """
    raw_chunks = [password[i:i+2] for i in range(len(password) - 1)]
    counts = Counter(raw_chunks)
    valid = []
    for c in raw_chunks:
        if counts[c] > 1:
            continue
        if c[0] == c[1]:
            continue
        if c[::-1] in raw_chunks:
            continue
        valid.append(c)
    return valid

# ---------------------------------------------------------------------- #

def get_direction(password, token):
    """
    Return 'before' or 'after' for the token based on its index in password chunk list.
    """
    chunks = get_password_tokens(password)
    idx = chunks.index(token)
    return 'before' if idx % 2 == 0 else 'after'

# ---------------------------------------------------------------------- #

def get_random_chunk_for_direction(password, direction):
    """
    Return a random valid password chunk for the requested direction.
    """
    chunks = get_password_tokens(password)
    if direction == "before":
        candidates = [chunks[i] for i in range(len(chunks)) if i % 2 == 0]
    else:
        candidates = [chunks[i] for i in range(len(chunks)) if i % 2 != 0]
    if not candidates:
        raise ValueError("No valid password chunks found for the given direction.")
    return random.choice(candidates)

# ---------------------------------------------------------------------- #

def get_random_decoy(password, exclude=None):
    """
    Return a decoy: reverse of a random password chunk.
    """
    chunk = random.choice(get_password_tokens(password))
    return chunk[::-1]

# ---------------------------------------------------------------------- #

def split_conflicting_message_tokens(message_tokens, password_tokens):
    """
    If a message token matches any password token (or reverse), split it into two chars.
    """
    password_set = set(password_tokens)
    password_rev_set = set(t[::-1] for t in password_tokens)
    result = []
    for tok in message_tokens:
        if (tok in password_set) or (tok in password_rev_set):
            if len(tok) == 2:
                result.extend([tok[0], tok[1]])
            else:
                result.append(tok)
        else:
            result.append(tok)
    return result

# ---------------------------------------------------------------------- #
#                        CHUNK PLACEMENT FUNCTIONS                      #
# ---------------------------------------------------------------------- #

def tightly_fit_chunks(lines, encoded_chunks):
    """
    Place all chunks in earliest available slots, left-to-right, no splits/overwrites.
    """
    n_lines = len(lines)
    line_len = len(lines[0])
    total_slots = n_lines * line_len
    flat = [tok for line in lines for tok in line]
    pos = 0
    for chunk in encoded_chunks:
        chunk_len = len(chunk)
        while pos <= total_slots - chunk_len:
            col_idx = pos % line_len
            if (col_idx + chunk_len <= line_len and
                all(flat[pos + i] is None for i in range(chunk_len))):
                for i, tok in enumerate(chunk):
                    flat[pos + i] = tok
                pos += chunk_len
                break
            else:
                pos += 1
        else:
            raise RuntimeError("No available slot for chunk in tight-fit fallback.")
    # Write back
    idx = 0
    for line in lines:
        for j in range(line_len):
            line[j] = flat[idx]
            idx += 1
    return lines

# ---------------------------------------------------------------------- #

def spread_chunks_with_fallback(lines, encoded_chunks, max_attempts=100, seed=None):
    """
    Try to spread chunks as evenly as possible; fall back to tight fit if needed.
    """
    n_lines = len(lines)
    line_len = len(lines[0])
    total_slots = n_lines * line_len

    def try_spread(flat, encoded_chunks):
        n_chunks = len(encoded_chunks)
        prev_end = -1
        for i, chunk in enumerate(encoded_chunks):
            length = len(chunk)
            # Assign bin
            start_bin = (i * total_slots) // n_chunks
            end_bin = ((i + 1) * total_slots) // n_chunks
            candidates = []
            # Try random order for flexibility
            positions = list(range(max(prev_end + 1, start_bin), end_bin - length + 1))
            random.shuffle(positions)
            for pos in positions:
                col_idx = pos % line_len
                if (col_idx + length <= line_len and
                    all(flat[pos + k] is None for k in range(length))):
                    candidates.append(pos)
            # Fallback: anywhere after prev_end
            if not candidates:
                positions = list(range(prev_end + 1, total_slots - length + 1))
                random.shuffle(positions)
                for pos in positions:
                    col_idx = pos % line_len
                    if (col_idx + length <= line_len and
                        all(flat[pos + k] is None for k in range(length))):
                        candidates.append(pos)
            if not candidates:
                return False  # failed
            chosen = candidates[0]
            for k in range(length):
                flat[chosen + k] = chunk[k]
            prev_end = chosen + length - 1
        return True

    # Try up to max_attempts
    for _ in range(max_attempts):
        flat = [tok for line in lines for tok in line]
        if try_spread(flat, encoded_chunks):
            # Copy back to lines
            idx = 0
            for line in lines:
                for j in range(line_len):
                    line[j] = flat[idx]
                    idx += 1
            return lines  # success!
    # Fallback
    return tightly_fit_chunks(lines, encoded_chunks)

# ---------------------------------------------------------------------- #
#                        ENCODER AND DECODER                             #
# ---------------------------------------------------------------------- #

def encode(text, password, line_max_tokens, total_max_tokens):
    # 1. Padding if needed
    needs_padding = (len(text) % 2 != 0)
    text_padded = text + random.choice(string.ascii_letters + string.digits) if needs_padding else text

    # 2. Tokenization
    message_tokens = get_text_tokens(text_padded)
    password_tokens = get_password_tokens(password)
    # message_tokens = split_conflicting_message_tokens(message_tokens, password_tokens) # not used, see design

    # 3. Encode chunks (pairs/trios)
    encoded_chunks = []
    for msg_token in message_tokens:
        chunk = []
        if msg_token in password_tokens:
            direction = get_direction(password, msg_token)
            if direction == "before":
                chunk.append(msg_token[::-1])
                chunk.append(msg_token)
                chunk.append(get_random_chunk_for_direction(password, 'before'))
            else:
                chunk.append(get_random_chunk_for_direction(password, 'after'))
                chunk.append(msg_token)
                chunk.append(msg_token[::-1])
        elif msg_token[::-1] in password_tokens:
            p_token = get_random_chunk_for_direction(password, 'after')
            if p_token != msg_token[::-1]:
                chunk.append(p_token)
                chunk.append(msg_token)
            else:
                chunk.append(msg_token)
                chunk.append(get_random_chunk_for_direction(password, 'before'))                       
        else:
            p_chunk = random.choice(password_tokens)
            if get_direction(password, p_chunk) == 'before':
                chunk.append(msg_token)
                chunk.append(p_chunk)
            else:
                chunk.append(p_chunk)
                chunk.append(msg_token)
        encoded_chunks.append(chunk)

    # 4. Setup lines buffer
    max_lines = int(total_max_tokens / line_max_tokens)
    if total_max_tokens % line_max_tokens != 0:
        max_lines += 1
    lines = []
    tmax_toks = total_max_tokens
    for _ in range(max_lines):
        if tmax_toks > line_max_tokens:
            lines.append([None] * line_max_tokens)
        else:
            lines.append([None] * tmax_toks)
        tmax_toks -= line_max_tokens

    # 5. Delete trick (padding): insert password token at start or end of a random line
    if needs_padding:
        p_chunk = random.choice(password_tokens)
        line_idx = random.randint(0, len(lines) - 1)
        if get_direction(password, p_chunk) == 'before':
            lines[line_idx][0] = p_chunk
        else:
            lines[line_idx][-1] = p_chunk

    # 6. Place encoded chunks
    spread_chunks_with_fallback(lines, encoded_chunks)

    # 7. Fill remaining Nones with noise
    for i, l in enumerate(lines):
        for j, k in enumerate(l):
            if k is None:
                lines[i][j] = generate_noise_token(password_tokens, message_tokens)

    return lines

# ---------------------------------------------------------------------- #

def decode(lines, password):
    valid_chunks = get_password_tokens(password)
    result = []
    delete_last = False

    for line in lines:
        for i, token in enumerate(line):
            if token in valid_chunks:
                chunk_idx = valid_chunks.index(token)
                direction = 'before' if chunk_idx % 2 == 0 else 'after'
                prev_chunk = line[i - 1] if i > 0 else ""
                next_chunk = line[i + 1] if i + 1 < len(line) else ""
                if direction == 'before':
                    candidate = prev_chunk
                else:
                    candidate = next_chunk

                if direction == "before":
                    if prev_chunk == '':
                        delete_last = True
                        continue
                    candidate = prev_chunk
                    if candidate[::-1] != token:
                        result.append(candidate)
                else:  # after
                    if next_chunk == '':
                        delete_last = True
                        continue
                    candidate = next_chunk
                    if candidate[::-1] != token:
                        result.append(candidate)

    res = ''.join(result)
    if delete_last:
        res = res[:-1]
    return res

# ---------------------------------------------------------------------- #
#                          PRINT/FORMAT HELPERS                          #
# ---------------------------------------------------------------------- #

def print_lines(lines):
    """
    Pretty print the token matrix, showing spaces as (spc), aligned.
    """
    processed = []
    for l in lines:
        row = []
        for c in l:
            if c is None:
                token = ''
            else:
                token = ''.join('(spc)' if ch == ' ' else ch for ch in c)
            row.append(token)
        processed.append(row)
    # Compute max width per column
    col_widths = [max(len(row[i]) for row in processed) for i in range(len(processed[0]))]
    # Print lines, column-aligned
    for row in processed:
        print(' | '.join(s.ljust(w) for s, w in zip(row, col_widths)))

# ---------------------------------------------------------------------- #

def parse_lines_arg(lines_args):
    """
    Given a list of strings like ["ABCDXY", "PQRSZZ"], returns a list of lists of 2-char tokens per line.
    """
    lines = []
    for line in lines_args:
        tokens = [line[i:i+2] for i in range(0, len(line), 2)]
        lines.append(tokens)
    return lines

# ---------------------------------------------------------------------- #

def lines_to_strings(lines):
    """
    For output: from list-of-list-of-tokens back to concatenated line strings.
    """
    return [''.join(line) for line in lines]

# ---------------------------------------------------------------------- #
#                              CLI MAIN ENTRY                            #
# ---------------------------------------------------------------------- #

def main():
    parser = argparse.ArgumentParser(description="Paper Coder (token-based)")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--encode", metavar="TEXT", help="Text message to encode")
    group.add_argument("--decode", action="store_true", help="Decode from token lines")

    parser.add_argument("--password", "-p", type=str, required=True, help="Password")
    parser.add_argument("--line-max", type=int, default=10, help="Max tokens per line (for encoding)")
    parser.add_argument("--total-max", type=int, default=30, help="Total token slots (for encoding)")
    parser.add_argument("--lines", nargs='*', help="Lines for decoding (each line as one string, e.g., 'AABBCC')")
    parser.add_argument("--print", action="store_true", help="Pretty print the token lines")

    args = parser.parse_args()

    if args.encode:
        text = args.encode
        password = args.password
        lines = encode(text, password, args.line_max, args.total_max)
        if args.print:
            print_lines(lines)
        # Print encoded lines as concatenated strings (for copy/paste)
        print("\n".join(lines_to_strings(lines)))

    elif args.decode:
        if not args.lines:
            print("Error: --lines must be provided for decode", file=sys.stderr)
            sys.exit(1)
        password = args.password
        lines = parse_lines_arg(args.lines)
        decoded = decode(lines, password)
        print(decoded)

# ---------------------------------------------------------------------- #

if __name__ == "__main__":
    main()
