#!/usr/bin/env python

import sys
import argparse
from ovirtsdk.api import API
from ovirtsdk.xml import params

# Base object
# =================================================
class Cmd_Base(object):
    def __init__(self, *args, **kwargs):
        self._api = None

    def connect(self, args):
        try:
            self._api = API(args.url, args.username, args.password, insecure=True)
        except Exception, e:
            print "Failed to connect to: %s" % args.url
            print e
            sys.exit(1)

    def __call__(self, args):
        self.connect(args)
        self.execute(args)

    def execute(self, args):
        raise NotImplementedError("Implement me sucka!")

# Test command
# =================================================
class Cmd_Test(Cmd_Base):
    def execute(self, args):
        try:
            assert self._api.test()
        except Exception, e:
            print "Failed to connect to: %s" % args.url
            print e
            return 1
        else:
            print "Success! Verified RHEV connectivity"
        return 0

# User commands
# =================================================
class Cmd_Users_List(Cmd_Base):
    def execute(self, args):
        users = self._api.users.list()
        if users:
            for u in users:
                print u.id, u.name, u.email
        else:
            raise Exception("No matching users found")

# VM commands
# =================================================
class Cmd_VMS_List(Cmd_Base):
    def execute(self, args):
        vms = self._api.vms.list(args.filter)
        if vms:
            for vm in vms:
                output = "%s [state:%s, memory:%s]" % (vm.name, vm.status.state, vm.memory >> 20)
                if vm.guest_info and vm.guest_info.ips:
                    output += " %s" % (", ".join([ip.address for ip in vm.guest_info.ips.ip]))
                print output
                for nic in vm.nics.list():
                    print " * %s/%s (%s)" % (nic.name, nic.interface, nic.mac.address)
        else:
            raise Exception("No matching vm's found")

class Cmd_VMS_Add(Cmd_Base):
    def execute(self, args):

        t = self._api.templates.get(args.template)
        assert t is not None, "Specified template '%s' not found" % args.template
        c = self._api.clusters.get(args.cluster)
        assert c is not None, "Specified cluster '%s' not found" % args.template

        # Determine VM name to use
        if args.name is not None:
            vm_name = args.name
        else:
            vm_name = args.template

        # List of existing VM names
        vm_names = [vm.name for vm in self._api.vms.list()]

        # Make sure VM name is unique
        count = 1
        while vm_name in vm_names:
            vm_name = "%s-%s" % (args.template, count)
            count += 1

        # Create VM
        print "Creating VM '%s'" % vm_name
        try:
            vm = params.VM(name=vm_name,
                    template=t,
                    cluster=c,)
            result = self._api.vms.add(vm)
        except Exception, e:
            print e
        else:
            print "VM '%s' created" % vm_name

class Cmd_VMS_Delete(Cmd_Base):
    def execute(self, args):

        # Delete VM
        print "Deleting VM '%s'" % args.name
        try:
            vm = self._api.vms.get(args.name)
            print vm.delete()
        except Exception, e:
            print e
        else:
            print "VM '%s' deleted" % args.name

class Cmd_VM_Add_Nic(Cmd_Base):
    def execute(self, args):
        # Create NIC object
        c = self._api.clusters.get(args.cluster)
        cluster_net = c.networks.get(args.network)
        nic = params.NIC(name=args.iface, network=cluster_net)

        # Add network to VM
        vm = self._api.vms.get(args.name)
        result = vm.nics.add(nic)

class Cmd_VM_Update(Cmd_Base):
    def execute(self, args):
        # Add network to VM
        vm = self._api.vms.get(args.name)
        for attr in ['memory']:
            if hasattr(args, attr):
                setattr(vm, attr, getattr(args, attr))
        result = vm.update()

class Cmd_VM(Cmd_Base):
    '''
    Handle VM sdk commands, such as [stop,start,shutdown,destroy]
    '''
    def execute(self, args):
        cmd = args.command.replace('vm.','')
        vm = self._api.vms.get(args.name)
        action = params.Action(async=True, vm=vm)
        if hasattr(vm, cmd):
            result = getattr(vm, cmd)(action)
        else:
            print "ERROR: unknown ovirtsdk command: vm.%s" % cmd

# StorageDomain commands
# =================================================
class Cmd_StorageDomains_List(Cmd_Base):
    def execute(self, args):
        sds = self._api.storagedomains.list(args.filter)
        if sds:
            if not args.noheader: print "%-15s %-40s %-10s %-10s %-40s" % ("NAME", "ID", "TYPE", "STATE", "DATACENTER")
            if not args.noheader: print "%-15s=%-40s=%-10s=%-10s=%-40s" % ("="*15, "="*40, "="*10, "="*10, "="*40)
            for sd in sds:
                if sd.status is None:
                    state = "???"
                else:
                    state = sd.status.state
                print "%-15s %-40s %-10s %-10s %-40s" % (sd.get_name(), sd.get_id(), sd.get_type(), state, sd.data_center)
        else:
            raise Exception("No matching storagedomains found")

class Cmd_StorageDomains_Add(Cmd_Base):
    def execute(self, args):
        # Access newly created storage domain
        local_sd = self._api.storagedomains.get(args.name)

        # Find datacenter object
        local_dc = self._api.datacenters.get(args.datacenter)

        # Find host object
        local_host = self._api.hosts.get(args.host)

        # Build storage parameter
        stParams = params.Storage(
                path=args.path,
                address=args.server,
                type_=args.type)

        # Build storage domain parameter
        sdParams = params.StorageDomain(
                name=args.name, #'local_export',
                data_center=local_dc,
                host=local_host,
                type_='export',
                storage=stParams,
                storage_format='v1')

        if self._api.storagedomains.add(sdParams):
            print 'Export Domain was created/imported successfully'

        # Access newly created storage domain
        local_sd = self._api.storagedomains.get(args.name)

class Cmd_StorageDomains_Attach(Cmd_Base):
    def execute(self, args):
        # Find datacenter object
        local_dc = self._api.datacenters.get(args.datacenter)

        # Access newly created storage domain
        local_sd = self._api.storagedomains.get(args.name)

        # Add to datacenter
        if local_dc.storagedomains.add(local_sd):
            print 'Export Domain was attached successfully'

class Cmd_StorageDomains_Activate(Cmd_Base):
    def execute(self, args):
        # Find datacenter object
        local_dc = self._api.datacenters.get(args.datacenter)

        # Activate!
        if local_dc.storagedomains.get(args.name).activate():
            print 'Export Domain was activated successfully'

class Cmd_StorageDomains_Deactivate(Cmd_Base):
    def execute(self, args):
        # Find datacenter object
        local_dc = self._api.datacenters.get(args.datacenter)

        # Activate!
        if local_dc.storagedomains.get(args.name).deactivate():
            print 'Export Domain was deactivated successfully'

    # TODO: storagedomains_detach
    # TODO: storagedomains_delete

class Cmd_StorageDomains_Templates_List(Cmd_Base):
    def execute(self, args):
        domains = self._api.storagedomains.list()
        if domains:
            output = list()
            for domain in domains:
                # FIXME - the filter doesn't apply at this level ... must reconcile with ovirtsdk
                for t in domain.templates.list(args.filter):
                    output.append("%-38s %-40s %-40s" % (t.id, t.name, domain.name))
            if output:
                if not args.noheader: print "%-38s %-40s %-40s" % ("Id", "Name", "Storage Domain")
                if not args.noheader: print "%-38s=%-40s=%-40s" % ("="*38, "="*40, "="*40)
                print "\n".join(output)
            else:
                raise Exception("No templates found")
        else:
            raise Exception("No storage domains found")

class Cmd_StorageDomains_Templates_Import(Cmd_Base):
    def execute(self, args):

        local_storage = self._api.storagedomains.get(args.dest)
        local_cluster = self._api.clusters.get(args.cluster)
        action = params.Action(async=False,
                cluster=local_cluster,
                storage_domain=local_storage)

        local_export = self._api.storagedomains.get(args.source)
        t = local_export.templates.get(args.name)
        print "Importing template %s ..." % t.get_name()
        action.template = t
        result = t.import_template(action)
        print result.get_status().get_state()

# Host commands
# =================================================
class Cmd_Hosts_List(Cmd_Base):
    def execute(self, args):
        s = "{id:<38} {name:<20} {state:<20}"
        if not args.noheader: print s.format(id="Id", name="Name", state="State")
        if not args.noheader: print s.replace(' ','=').format(id='='*38, name='='*20, state='='*20)
        for host in self._api.hosts.list(args.filter):
            print s.format(id=host.id, name=host.name, state=host.status.state)

# Cluster commands
# =================================================
class Cmd_Clusters_List(Cmd_Base):
    def execute(self, args):
        s = "{id:<38} {name:<20}"
        if not args.noheader: print s.format(id="Id", name="Name")
        if not args.noheader: print s.replace(' ','=').format(id='='*38, name='='*20)
        for clstr in self._api.clusters.list(args.filter):
            print s.format(id=clstr.id, name=clstr.name)

# Datacenter commands
# =================================================
class Cmd_Datacenters_List(Cmd_Base):
    def execute(self, args):
        dcs = self._api.datacenters.list(args.filter)
        if dcs:
            s = "{id:<38} {name:<20} {state:<20}"
            if not args.noheader: print s.format(id="Id", name="Name", state="State")
            if not args.noheader: print s.replace(' ','=').format(id='='*38, name='='*20, state='='*20)
            for dc in self._api.datacenters.list(args.filter):
                print s.format(id=dc.id, name=dc.name, state=dc.status.state)
        else:
            raise Exception("No datacenters found")

# Template commands
# =================================================
class Cmd_Templates_List(Cmd_Base):
    def execute(self, args):
        templates = self._api.templates.list(args.filter)
        if templates:
            if not args.noheader: print "%-38s %-20s %-15s" % ("Id", "Name", "Origin")
            if not args.noheader: print "%-38s=%-20s=%-15s" % ("="*38, "="*30, "="*15)
            for t in templates:
                print "%-38s %-20s %-15s" % (t.id, t.name, t.origin)
        else:
            raise Exception("No matching templates found")

def parse_args():

    parser = argparse.ArgumentParser(usage='%s <options> [command] '
            '<command-options>' % sys.argv[0])

    # Global arguments
    parser.add_argument("--url", dest="url",
            default=None, metavar="URL", required=True,
            help="RHEVM host in the form of https://localhost/api")
    parser.add_argument("-u", "--username", dest="username",
            default=None, metavar="USERNAME", required=True,
            help="RHEVM username")
    parser.add_argument("-p", "--password", dest="password",
            default=None, metavar="PASSWORD", required=True,
            help="RHEVM password")
    parser.add_argument("--noheader", dest="noheader",
            default=False, action='store_true',
            help="Disable output header")

    # Define shared arguments
    parser_filter = argparse.ArgumentParser(add_help=False)
    parser_filter.add_argument('-f', '--filter',
        default=None, dest='filter',
        help='Specify filter as key=value pairs')

    parser_name = argparse.ArgumentParser(add_help=False)
    parser_name.add_argument('--name', dest='name',
        metavar='NAME', default=None, required=True,
        help="Specify name of desired item")

    parser_datacenter = argparse.ArgumentParser(add_help=False)
    parser_datacenter.add_argument('--datacenter', dest='datacenter',
        metavar='DATACENTER', default="local_datacenter",
        help="Specify datacenter (default: %(default)s)")

    parser_template = argparse.ArgumentParser(add_help=False)
    parser_template.add_argument('--template', dest='template',
        metavar='TEMPLATE', default=None, required=True,
        help="Specify template (default: %(default)s)")

    parser_cluster = argparse.ArgumentParser(add_help=False)
    parser_cluster.add_argument('--cluster', dest='cluster',
        metavar='CLUSTER', default="local_cluster",
        help="Specify cluster (default: %(default)s)")

    # Command-specific options
    subparsers = parser.add_subparsers(dest='command')
    p = subparsers.add_parser('test',
            help='Test connectivity to RHEVM server')
    p.set_defaults(function=Cmd_Test)

    p = subparsers.add_parser('users', parents=[parser_filter],
            help='List available Users')
    p.set_defaults(function=Cmd_Users_List)

    p = subparsers.add_parser('vms.list', parents=[parser_filter],
            help='List available VMs')
    p.set_defaults(function=Cmd_VMS_List)

    p = subparsers.add_parser('vms.add',
            parents=[parser_name, parser_template, parser_cluster],
            help='Create VM from specified template')
    p.set_defaults(function=Cmd_VMS_Add)

    p = subparsers.add_parser('vm.add.nic',
            parents=[parser_name, parser_cluster],
            help ='Add network adapter to specified VM')
    p.add_argument('--iface', dest='iface',
            metavar='IFACE', default="eth0",
            help="Specify interface name (default: %(default)s)")
    p.add_argument('--network', dest='network',
            metavar='NETWORK', default="rhevm",
            help="Specify cluster network name (default: %(default)s)")
    p.set_defaults(function=Cmd_VM_Add_Nic)

    class convert_mib2b(argparse.Action):
        def __call__(self, parser, namespace, value, option_string=None):
            '''
            convert value from Mib to bytes.  For example, 1 MiB becomes 1048576 bytes
            '''
            setattr(namespace, self.dest, value << 20)

    p = subparsers.add_parser('vm.update',
            parents=[parser_name],
            help ='Update specified VM')
    p.add_argument('--memory', dest='memory', type=int,
            metavar='MEMORY', default=None, action=convert_mib2b,
            help="Specify VM memory in MB")
    p.set_defaults(function=Cmd_VM_Update)

    p = subparsers.add_parser('vm.start',
            parents=[parser_name],
            help ='Start specified VM')
    p.set_defaults(function=Cmd_VM)

    p = subparsers.add_parser('vm.stop',
            parents=[parser_name],
            help ='Stop specified VM')
    p.set_defaults(function=Cmd_VM)

    p = subparsers.add_parser('vm.shutdown',
            parents=[parser_name],
            help ='Shutdown specified VM')
    p.set_defaults(function=Cmd_VM)

    p = subparsers.add_parser('vm.delete',
            parents=[parser_name],
            help ='Delete specified VM')
    p.set_defaults(function=Cmd_VM)

    p = subparsers.add_parser('storagedomains.list',
            parents=[parser_filter],
            help ='List available Storage Domains')
    p.set_defaults(function=Cmd_StorageDomains_List)

    p = subparsers.add_parser('storagedomains.add',
            parents=[parser_name, parser_datacenter],
            help ='Add specified Storage Domain')
    p.add_argument('--host', metavar='HOST', default="local_host",
            help="Specify host name (default: %(default)s)")
    p.add_argument('--path', metavar='PATH', default="/export",
            help="Specify domain path (default: %(default)s)")
    p.add_argument('--server', metavar='SERVER', default="localhost",
            help="Specify domain server (default: %(default)s)")
    p.add_argument('--type', metavar='TYPE', default="nfs",
            help="Specify domain type (default: %(default)s)")
    p.set_defaults(function=Cmd_StorageDomains_Add)

    p = subparsers.add_parser('storagedomains.attach',
            parents=[parser_name, parser_datacenter],
            help ='Attach specified Storage Domain')
    p.set_defaults(function=Cmd_StorageDomains_Attach)

    p = subparsers.add_parser('storagedomains.activate',
            parents=[parser_name, parser_datacenter],
            help ='Activate specified Storage Domain')
    p.set_defaults(function=Cmd_StorageDomains_Activate)

    p = subparsers.add_parser('storagedomains.deactivate',
            parents=[parser_name, parser_datacenter],
            help ='Deactivate specified Storage Domain')
    p.set_defaults(function=Cmd_StorageDomains_Deactivate)

    p = subparsers.add_parser('storagedomains.templates.list',
            parents=[parser_filter],
            help ='List templates associated with a Storage Domains')
    p.set_defaults(function=Cmd_StorageDomains_Templates_List)

    p = subparsers.add_parser('storagedomains.templates.import',
            parents=[parser_name, parser_cluster],
            help ='Import specified template into desired Storage Domains')
    p.add_argument('--source', metavar='SOURCE',
            default="local_export",
            help="Specify source domain (default: %(default)s)")
    p.add_argument('--dest', metavar='DEST',
            default="local_storage",
            help="Specify target domain (default: %(default)s)")
    p.set_defaults(function=Cmd_StorageDomains_Templates_Import)

    p = subparsers.add_parser('templates.list',
            parents=[parser_filter],
            help ='List available templates')
    p.set_defaults(function=Cmd_Templates_List)

    p = subparsers.add_parser('clusters.list',
            parents=[parser_filter],
            help ='List available clusters')
    p.set_defaults(function=Cmd_Clusters_List)

    p = subparsers.add_parser('hosts.list',
            parents=[parser_filter],
            help ='List available hosts')
    p.set_defaults(function=Cmd_Hosts_List)

    p = subparsers.add_parser('datacenters.list',
            parents=[parser_filter],
            help ='List available hosts')
    p.set_defaults(function=Cmd_Datacenters_List)

    args = parser.parse_args()

    if args.url is None:
        parser.error("Missing required --url parameter")
    if args.username is None:
        parser.error("Missing required --username parameter")
    if args.password is None:
        parser.error("Missing required --password parameter")

    if args.command is None or args.command == '':
        parser.error("No command provided")

    return args

if __name__ == '__main__':

    try:
        args = parse_args()
        if not hasattr(args, 'function'):
            raise NotImplementedError("No function defined for command: %s" % args.command)
        args.function()(args)
    except Exception, e:
        print e
        rc = 1
    else:
        rc = 0

    sys.exit(rc)
