#!/bin/sh

# Add custom hosts entries
echo '10.1.1.71 demo.cm2020.laravel # CM Helpdesk' >> /etc/hosts
echo '10.1.1.71 guestview.cm2021.laravel # CMGuest' >> /etc/hosts
echo '10.1.1.71 api.cm2021.laravel # CMGuest API' >> /etc/hosts

# Run the Streamlit app
exec "$@"