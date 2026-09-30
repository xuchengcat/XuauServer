1. Apply 00-installer-config.yaml to /etc/netplan/00-installer-config.yaml
2. try pppoe service to get the correct accress, make sure get the public IPV6
3. Apply dhcp.conf to /etc/dnsmasq.d/dhcp.conf for DHCP and DNS settings
4. do ip config settings
5. install wide-dhcpv6-client to send ra out get IPV6
5. install shellclash with cmd 

IPv6 LAN address note (2026-09-28):
- The VS010 device "unwifi" (MAC 58:95:D8:1A:83:1A) incorrectly responds to
  fc00:192:168:2::1, while its DHCPv6 reservation is fc00:192:168:2::30.
- br_lan therefore uses fc00:192:168:2::100/64. This address is outside the
  stateful DHCPv6 pool fc00:192:168:2::2 through fc00:192:168:2::ff.
- dnsmasq advertises fc00:192:168:2::100 as the IPv6 DNS and NTP server.
- Applied and verified on 2026-09-28: DAD passed, br_lan reached
  "routable (configured)", an isolated LAN client resolved ::100 to server
  MAC 6A:B9:69:50:50:AF, ICMPv6 had 0% loss, DNS returned NOERROR, and RA
  advertised ::100 as its recursive DNS server.
- Pre-change versions remain available in Git history.

IPv4 reservation note (2026-09-28):
- 192.168.2.100 is reserved to correspond with the server IPv6 service address
  fc00:192:168:2::100 and must not be dynamically leased.
- The IPv4 dynamic DHCP pool therefore starts at 192.168.2.101 and ends at
  192.168.2.254.
