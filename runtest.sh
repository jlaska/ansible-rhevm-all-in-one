#!/bin/bash
#
# Sample beaker runtest.sh task to execute ansible playbooks in a beaker job.
# For more information on beaker, refer to http://beaker-project.org.
#
# Requirements:
#  * beakerlib - https://fedorahosted.org/beakerlib/
#

# -----------------------------------------------------------------------------
# Import RHTS and beakerlib
# -----------------------------------------------------------------------------
# If available, source rhts-environment
if [ -f /usr/bin/rhts-environment.sh ]; then
    source /usr/bin/rhts-environment.sh
fi

# If available, source beakerlib
for IMPORT in /usr/lib/beakerlib/beakerlib.sh \
              /usr/share/beakerlib/beakerlib.sh ;
do
    if [ -f "${IMPORT}" ]; then
        source ${IMPORT}
    fi
done

# Perform any required cleanup on exit
cleanup() {
    # Close out any running beakerlib test phase
    rlPhaseEnd
    rlJournalEnd
    rlJournalPrintText
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

rlJournalStart

# Run cleanup when we exit.  NOTE: if you remove the trap on EXIT, cleanup()
# needs to be called manually # to properly close out the beakerlib journal
trap cleanup EXIT

rlPhaseStartSetup "Install ansible"

# Install ansible
if ! rlCheckRpm ansible; then
    # Enable EPEL if needed
    if rlIsRHEL ; then
        rlRun "yum -y install 'http://download.fedoraproject.org/pub/epel/6/i386/epel-release-6-8.noarch.rpm'"
    fi
    rlRun "yum -y install ansible"

    if ! rlCheckRpm ansible; then
       rlLogError "ERROR: failed to install ansible"
       exit 1
    fi
fi

# Checkout playbook

REPO_URL="https://github.com/jlaska/ansible-rhevm-all-in-one.git"
REPO_NAME=${REPO_URL##*/}
REPO_NAME=${REPO_NAME%.git}
rlRun "test -d $REPO_NAME && ( cd $REPO_NAME && git pull ) || (git clone $REPO_URL && cd $REPO_NAME )"

rlPhaseEnd

rlPhaseStartSetup "Run ansible playbook"

readonly ANSIBLE_PLAYBOOK=${1:-site.yml}

# Build ansible '-e' parameter
EXTRA_VARS=$(env | while read KEYVAL ;
do
    # Skip unless it starts with 'ANSIBLE_'
    [[ $KEYVAL =~ ANSIBLE_* ]] || continue

    # Strip leading 'ANSIBLE_' text
    KEYVAL=${KEYVAL#ANSIBLE_}

    # Append "key.lower() = value"
    IFS="="
    set -- $KEYVAL
    echo -n "${1,,}=$2 "
    unset IFS
done)

# Assemble argument string
ANSIBLE_ARGS="-i inventory"
if [ -n "$EXTRA_VARS" ]; then
   ANSIBLE_ARGS="-e \"$EXTRA_VARS\" $ANSIBLE_ARGS"
fi

# Run ansible
rlRun "ansible-playbook ${ANSIBLE_ARGS} $ANSIBLE_PLAYBOOK"

rlPhaseEnd
