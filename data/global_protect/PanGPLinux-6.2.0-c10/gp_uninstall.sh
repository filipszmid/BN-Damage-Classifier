#!/bin/bash

# Determine command type
cmd_type="ui"
if [ $# -gt 0 ]; then
    case $1 in
    --cli-only)
        cmd_type="cli-only";;
    --arm)
        cmd_type="arm";;
    --help)
	;&
    *)
        cmd_type="usage";;
    esac
fi

# Determine Linux Distro and Version
. /etc/os-release

if [ $ID == "ubuntu" ]; then
    linux_ver=${VERSION_ID:0:2}
elif [[ $ID == "rhel" || $ID == "centos" ]]; then
    linux_ver=${VERSION_ID:0:1}
fi

case $cmd_type in
    cli-only)
        # CLI Only Uninstall
        case $ID in
            ubuntu)
                apt-get -y remove globalprotect
		;;
            rhel)
                ;&
            fedora)
                ;&
            centos)
                case $linux_ver in
                    7)
			yum -y remove GlobalProtect_rpm
                        ;;
		    *)
			yum -y remove GlobalProtect_focal_rpm
			;;
	        esac
	        ;;
            *)
            echo "Error: Unsupported Linux Distro: $ID"
	    exit
            ;;
        esac
        ;;

    arm)
        # ARM Uninstall
        case $ID in
            ubuntu)
                apt-get -y remove globalprotect
                ;;
            rhel)
                ;&
            fedora)
                ;&
            centos)
                case $linux_ver in
                    7)
                        yum -y remove GlobalProtect_rpm_arm
                        ;;
		    *)
                        yum -y remove GlobalProtect_focal_rpm_arm
			;;
	        esac
	        ;;
            *)
            echo "Error: Unsupported Linux Distro: $ID"
	    exit
            ;;
        esac
        ;;

    ui)
        # UI Uninstall
        case $ID in
            ubuntu)
                apt-get -y remove globalprotect
                ;;
            rhel)
                ;&
            fedora)
                ;&
            centos)
		# Install
                case $linux_ver in
                    7)
                        yum -y remove GlobalProtect_UI_rpm
                        ;;
		    *)
                        yum -y remove GlobalProtect_UI_focal_rpm
			;;
	        esac
	        ;;
            *)
            echo "Error: Unsupported Linux Distro: $ID"
            ;;
        esac
        ;;
    usage)
	;&
    *)
        echo "Usage: $ sudo ./gp_uninstall [--cli-only | --arm | --help]"
        echo "  --cli-only: CLI Only"
        echo "  --arm:      ARM"
        echo "  no options: UI"
        ;;	
esac
