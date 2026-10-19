#!/bin/sh
# The real Integrator (a pure function from a Run Context to a verdict plus a branch).
#
#   integrator.sh CTX
#
# CTX holds clones `base`, `main`, `implementor` and `acceptance-writer`. It writes the verdict to
# CTX/verdict/{result,failed_check,spec_output,output} and, on green, the integrated clone to CTX/result.
# `output` is the Acceptance Report or the merge output, verbatim. Exit status is non-zero only when
# the Integrator itself could not run.
set -u
ctx=$1
v=$ctx/verdict
mkdir -p "$v"
: > "$v/spec_output"

identity() {
    git -C "$1" config user.name Integrator
    git -C "$1" config user.email integrator@example.invalid
}

red() { # failed_check, output file
    echo red > "$v/result"
    printf %s "$1" > "$v/failed_check"
    cp "$2" "$v/output"
    exit 0
}

# 1. The new specs must be red on base: base plus the Acceptance Writer's changes must fail `make test`.
git clone -q "$ctx/base" "$ctx/specs" || exit 1
identity "$ctx/specs"
git -C "$ctx/specs" fetch -q "$ctx/acceptance-writer" HEAD || exit 1
git -C "$ctx/specs" merge -q --no-edit FETCH_HEAD > "$v/log" 2>&1 || exit 1
if (cd "$ctx/specs" && make test) > "$v/spec_output" 2>&1; then
    red specs-not-red "$v/spec_output"
fi

# 2. Combine the branches on top of the latest main. A conflict fails the Run.
git clone -q "$ctx/main" "$ctx/result" || exit 1
identity "$ctx/result"
for role in implementor acceptance-writer; do
    git -C "$ctx/result" fetch -q "$ctx/$role" HEAD || exit 1
    if ! git -C "$ctx/result" merge --no-edit -m "Integrate $role" FETCH_HEAD > "$v/merge" 2>&1; then
        git -C "$ctx/result" merge --abort
        red conflict "$v/merge"
    fi
done

# 3. The entire acceptance suite on the integrated result.
if (cd "$ctx/result" && make test) > "$v/output" 2>&1; then
    echo green > "$v/result"
else
    red suite "$v/output"
fi
