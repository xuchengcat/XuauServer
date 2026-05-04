#!/bin/bash
# firewall-set.sh
# 参考3.6小节

# 根据你的WAN网卡名称对应修改！！！
WAN_NAME='pppoe_dial'

#some ubuntu version not forward default, need add this to forward request
iptables -P FORWARD ACCREPT

# IPv4设置
iptables -t nat -N mt_rtr_4_n_rtr
iptables -t nat -A POSTROUTING -j mt_rtr_4_n_rtr
iptables -t nat -A mt_rtr_4_n_rtr -o ${WAN_NAME} -j MASQUERADE # 添加路由到作为WAN的网卡的自动源地址转换规则

# 添加IPv4转发优化规则
iptables -t mangle -N mt_rtr_4_m_rtr 
iptables -t mangle -A FORWARD -j mt_rtr_4_m_rtr
iptables -t mangle -A mt_rtr_4_m_rtr -o ${WAN_NAME} -p tcp -m tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu # 针对PPPoE链接的优化
iptables -t mangle -A mt_rtr_4_m_rtr -m state --state RELATED,ESTABLISHED -j ACCEPT # 允许已建立连接的数据包直接通过
iptables -t mangle -A mt_rtr_4_m_rtr -m conntrack --ctstate INVALID -j DROP
iptables -t mangle -A mt_rtr_4_m_rtr -p tcp -m tcp ! --tcp-flags FIN,SYN,RST,ACK SYN -m state --state NEW -j DROP
iptables -t mangle -A mt_rtr_4_m_rtr -p tcp -m tcp --tcp-flags FIN,SYN,RST,PSH,ACK,URG FIN,SYN,RST,PSH,ACK,URG -j DROP
iptables -t mangle -A mt_rtr_4_m_rtr -p tcp -m tcp --tcp-flags FIN,SYN,RST,PSH,ACK,URG NONE -j DROP
iptables -t mangle -A mt_rtr_4_m_rtr -i br_lan -o ${WAN_NAME} -j ACCEPT

# IPv6 NAT设置，与IPv4基本一致
ip6tables -t nat -N mt_rtr_6_n_rtr
ip6tables -t nat -A POSTROUTING -j mt_rtr_6_n_rtr
ip6tables -t nat -A mt_rtr_6_n_rtr -o ${WAN_NAME} -j MASQUERADE # 添加路由到作为WAN的网卡的自动源地址转换规则

# 添加IPv6转发优化规则
ip6tables -t mangle -N mt_rtr_6_m_rtr
ip6tables -t mangle -A FORWARD -j mt_rtr_6_m_rtr
ip6tables -t mangle -A mt_rtr_6_m_rtr -o ${WAN_NAME} -p tcp -m tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu
ip6tables -t mangle -A mt_rtr_6_m_rtr -m state --state RELATED,ESTABLISHED -j ACCEPT
ip6tables -t mangle -A mt_rtr_6_m_rtr -m conntrack --ctstate INVALID -j DROP
ip6tables -t mangle -A mt_rtr_6_m_rtr -p tcp -m tcp ! --tcp-flags FIN,SYN,RST,ACK SYN -m state --state NEW -j DROP
ip6tables -t mangle -A mt_rtr_6_m_rtr -p tcp -m tcp --tcp-flags FIN,SYN,RST,PSH,ACK,URG FIN,SYN,RST,PSH,ACK,URG -j DROP
ip6tables -t mangle -A mt_rtr_6_m_rtr -p tcp -m tcp --tcp-flags FIN,SYN,RST,PSH,ACK,URG NONE -j DROP
ip6tables -t mangle -A mt_rtr_6_m_rtr -i br_lan -o ${WAN_NAME} -j ACCEPT

#enable ICMPv6 bypass
iptables -A INPUT -p ipv6-icmp -j ACCEPT
iptables -A FORWARD -p ipv6-icmp -j ACCEPT
iptables -A OUTPUT -p ipv6-icmp -j ACCEPT
ip6tables -A INPUT -p ipv6-icmp -j ACCEPT
ip6tables -A FORWARD -p ipv6-icmp -j ACCEPT
ip6tables -A OUTPUT -p ipv6-icmp -j ACCEPT
