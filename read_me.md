All whole music files (.mp3) to go in tools/music

python tools/distribute.py --peers 50 --replication 3

python tools/split.py (need to change the music file name)

python tracker.py
python peer.py <peer_number>



Docker:

python tools/distribute.py -n 50 -r 3

docker-compose down --remove-orphans

docker-compose build

docker-compose up -d tracker

./docker-run-peers.sh


# Setup:
python tools/distribute.py -n 50 -r 3

docker-compose down --remove-orphans
docker-compose build
./docker-run-peers.sh  

# Cold Start :
python tools/sim_cold_start.py -f in_the_light.mp3 -n 50 -o tools/sim_csv/sim_cold_start.csv

# Churn :
python tools/sim_churn.py -n 50 -r 5 -d 360 -o tools/sim_csv/churn5.csv 

# Peer starvation : 
python tools/distribute_starvation.py --peers 50 --seed 1

# Partial distribution:
python tools/distribute_partial.py --peers 50 --replication 3 --missing 0.3

# Bandwidth saturation:
tools/limit_bandwidth.sh 50 100mbit

# verify cc algo:
docker exec -it peer2 sh -c "python - << 'PY'
import ssl, socket
import sys, os
sys.path.insert(0, '/app')         
import peer                        
s = socket.socket()
algo = s.getsockopt(socket.IPPROTO_TCP, socket.TCP_CONGESTION, 16)
print('Patched socket CC →', algo.rstrip(b'\\x00').decode())
PY"