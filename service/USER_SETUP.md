# HVE — Mercury service units (D6=B: dedicated `hve` user)

# Create on Mercury:
#   sudo useradd --system --no-create-home --shell /usr/sbin/nologin hve
#   sudo mkdir -p /home/hve/.hve/{data,knowledge,reports,backups,hve-restore}
#   sudo chown -R hve:hve /home/hve/.hve

# /home/hermes/.hve -> shared with hermes via group (optional later)

[Install]
WantedBy=multi-user.target
