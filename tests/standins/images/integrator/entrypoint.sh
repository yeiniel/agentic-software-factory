# Stub for the Integrator entrypoint: a canned verdict chosen by the Context's `script` file.
ls /sys/class/net > /ctx/interfaces
mkdir -p /ctx/verdict /ctx/result
case "$(cat /ctx/script 2> /dev/null)" in
    HANG) sleep 60 ;;
    RED) echo red > /ctx/verdict/result; echo suite > /ctx/verdict/failed_check
         echo "spec out" > /ctx/verdict/spec_output; echo "suite out" > /ctx/verdict/output; exit 1 ;;
    NONE) exit 5 ;;
    *) echo green > /ctx/verdict/result; echo "suite green" > /ctx/verdict/output ;;
esac
