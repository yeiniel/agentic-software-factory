# `mail` can't encode a message without a character set, and Postfix runs the
# commands it delivers to with LANG=C: a login sets it again.
export LANG=C.UTF-8
