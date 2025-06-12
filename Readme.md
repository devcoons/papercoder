# Paper Coder

A minimal, extensible, password-based **encoding** and **decoding** tool for hiding messages in plain text, line-by-line, using a token-mixing scheme for paper puzzles.

---

## What Is It?

**Paper Coder** lets you encode (obfuscate) a message using a password.  
You can then decode (recover) the message only with the correct password.  
It works by splitting the message into tokens, mixing them with password-derived tokens and noise, and outputting them in lines.

- **Encoding:** hides a message using a password and outputs lines of mixed tokens.  
- **Decoding:** restores the message from those lines, using the same password.

While it resembles encryption, it is better described as a **password-based encoding/decoding scheme**:  
It is *not* cryptographically secure and should not be used for sensitive information!

---

## Usage

Paper Coder is a command-line Python application.

### Encoding a Message

```sh
python papercoder.py --encode "SecretMessage123" --password "YourPassword" --line-max 10 --total-max 30 --print
```

- `--encode`: the message you want to hide.
- `--password` or `-p`: the password for encoding/decoding.
- `--line-max`: max number of tokens per output line (default: 10).
- `--total-max`: total number of tokens in all lines (default: 30).
- `--print`: (optional) prints a pretty matrix of the encoded lines.

**The output will be several lines of uppercase/lowercase letters and digits.**  
**Save these lines!** They are needed for decoding.

---

### Decoding a Message

Suppose you have these lines (output from encoding):

```
XyJgV0RmT0
WaG5kC1LwX
```

To decode:

```sh
python papercoder.py --decode --password "YourPassword" --lines "rdSeiYWcl3crPaeturzh" "E7rQMeYok7VJassslK62" "agswQF7Ge1Yob623uro1"
```

- Pass each encoded line as a separate string after `--lines`.
- The original message will be printed.

---

## Terminology

- **Encode/Decode:** Technically correct for this tool, since it's not strong cryptography.
- **Encrypt/Decrypt:** Would be misleading; this tool is *not* cryptographically secure.

---

## Security Warning

This tool is **not** intended for strong security.  
It is suitable for obscuring messages or paper-based puzzles, **not** for protecting secrets against determined attackers.

---

## Requirements

- Python 3.11+

---

## License

MIT