Sure thing, here are the steps as best as I remember them:

1. SSH into your Raspberry Pi Zero 2 W.
2. Run the following to enable PWM: `sudo raspi-config nonint do_spi 0`
3. Run the following to download a Hyperion docker repository (disclaimer: this is not my repository): `git clone https://github.com/foorschtbar/hyperion-docker`
4. Run `cd hyperion-docker`
5. Create "docker-compose.yaml" with the following contents:
```
services:
  hyperion:
    image: foorschtbar/hyperion
    container_name: hyperion
    privileged: true
    ports:
      - 8090:8090
      - 8092:8092
      - 19400:19400
      - 19444:19444
      - 19445:19445
    volumes:
      - ./config/:/root/.hyperion
    restart: unless-stopped
```
6. Run `docker build -t hyperion --no-cache .`
7. Run `docker compose up -d`
8. Run `docker ps`.  Make a note of the Container ID of your docker for the table software (not the Container ID for the new Hyperion docker).
9. Run `docker exec -ti <table Container ID> sh`
10. Run `cd modules`
11. Run `cd led`
12. Replace the contents of led_controller.py with the code at the following link: https://github.com/tlchandler/dwp_hyperion_led/blob/main/led_controller.py.  Note that some of this code was vibe-coded and some of it was human-coded, but it seems to work.  Very importantly, note the comment in the WLED_TO_HYPERION_PRESET_MAP and a change you might want to make.
13. You can close SSH.
14. Your Hyperion server should be up and running.  Go to `http://<raspberry pi ip address>:8090`.
15. Go to LED Instances > LED Output > LED Controller and set Controller Type to WS281X, GPIO number to 12, and Hardware LED count to 133.
16. Go to LED Instances > Effects and set whether to Activate an effect on boot or not.
17.  Go to Network Services  and disable API Authentication and Local Admin API Authentication.  Don't blame me if this means that someone can hack your lights.
18.  Go to Effects Configurator.  Using the Delete/Load Effect on the right side, load the effect you want to use and modify it.  Name the table idle effect Preset01 and the table moving effect Preset02.
19. Go to http://`<raspberry pi ip address>:8080`.  Click the gear settings icon.  Under WLED configuration, put the IP of your raspberry pi (don't use localhost or 127.0.0.1; those don't work for some reason).
20. Connect your LED strip's green pin to GPIO 12 on your pi.
21. Presto, it should be working.  Note that you won't be able to access the LED config within the table website anymore (unlike how Tuan had it coded, which was cool), but you can still modify your presets at the :8090 port mentioned above.

Let me know of any questions.
