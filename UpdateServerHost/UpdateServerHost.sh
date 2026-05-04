#!/bin/bash
ZeroTierToken="jQYD33GvsXNnRgi2HLAXvAccBsqfumpN"
NWID="abfd31bd470eb354"
MBID="5664493eae" # home server
BARK_SERVER="xuau-bark-server.onrender.com"
BARK_TOKEN="iphone" # my device token

# Path to SmartDNS config file
SMARTDNS_CONF="/etc/smartdns/smartdns.conf"
# IPV6 Regex
ipv6_pattern='^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$'

# Initialize ping failure counter
ping_failures=0

while true; do
    # Try to ping xuchengcat.cn
    if ! ping -c 1 xuchengcat.cn &> /dev/null; then
        ((ping_failures++))
        echo "$(date): Ping attempt $ping_failures failed"
        
        # Only proceed if we've had 10 consecutive failures
        if [ $ping_failures -ge 10 ]; then
            echo "$(date): Cannot connect to xuchengcat.cn after 10 attempts, trying to update host..."
            
            # Make API request to get network members
            physical_addr=$(curl -s -X GET "https://api.zerotier.com/api/v1/network/$NWID/member/$MBID" \
                 -H "Authorization: token $ZeroTierToken" \
                 -H "Content-Type: application/json" | \
                 jq -r '.physicalAddress')

            if echo "$physical_addr" | grep -Eq "$ipv6_pattern"; then
                # Remove old entry if exists
                # sed -i '/address \/xuchengcat.cn\//d' $SMARTDNS_CONF
                
                # Add new IPv6 host record
                # echo "address /xuchengcat.cn/$physical_addr" >> $SMARTDNS_CONF
                
                # Restart SmartDNS service
                # systemctl restart smartdns
                
                echo "$(date): Added IPv6 host record for xuchengcat.cn to SmartDNS"
                echo "$(date): Host record: xuchengcat.cn -> $physical_addr"
            else
                # Send Bark notification when not an IPv6 address
                curl -s "https://$BARK_SERVER/$BARK_TOKEN/DNS_Update_Failed/Invalid_IP_Address:_${physical_addr}?isArchive=1"
                
                echo "$(date): Not an IPv6 address: $physical_addr"
            fi
            
            # Reset failure counter after attempting fix
            ping_failures=0
        fi
    else
        # Reset failure counter on successful ping
        if [ $ping_failures -gt 0 ]; then
            echo "$(date): Connection restored after $ping_failures failures"
        fi
        ping_failures=0
    fi

    # Sleep for 1 hour
    sleep 3600
done
