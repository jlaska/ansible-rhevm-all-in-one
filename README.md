ansible-rhevm-all-in-one
========================

[Ansible](http://ansible.cc/) playbook for deploying a RHEV/oVirt single-host all-in-one instance.

## ansible-cfme repository/structure

 * files - files and templates for use in playbooks/tasks
 * group_vars - customize deployment by setting/replacing variables
 * handlers - common service handlers
 * library - library of custom local ansible modules
 * tasks - snippets of tasks that should be included in plays

## Dependencies
 * [ansible-1.2](https://github.com/ansible/ansible) (or newer)

## Instructions
1. Clone this repo

        git clone https://github.com/jlaska/ansible-rhevm-all-in-one.git

2. Run the playbook:

        ansible-playbook -i inventory site.yml

Please send me feedback by way of gitbug issues.  Pull requests encouraged!
