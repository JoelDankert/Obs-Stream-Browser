
#!/usr/bin/env bash

# Navigate to your project root
cd ~/MediaMTX || exit 1

# Launch server.py in a new Alacritty window
alacritty --title "HostControl Server" -e bash -c "
echo '🔧 Starting server.py...';
python3 server.py;
echo '❌ server.py exited. Press Enter to close.';
read
" &

# Small delay so windows don’t spawn on top of each other
sleep 1

# Launch MediaMTX in a new Alacritty window
alacritty --title "MediaMTX" -e bash -c "
echo '🎥 Starting MediaMTX...';
./mediamtx;
echo '❌ MediaMTX exited. Press Enter to close.';
read
" &
