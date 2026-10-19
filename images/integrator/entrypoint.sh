# The Run Context is mounted at /ctx; the verdict is left in /ctx/verdict and the result in /ctx/result.
git config --global safe.directory '*'
exec sh /opt/asf/integrator.sh /ctx
