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


# Cold Start :
docker-compose down --remove-orphans
python tools/distribute.py -n 50 -r 3
docker-compose build
./docker-run-peers.sh    &&    python tools/sim1_cold_start.py -f comf_numb.mp3 -n 50 -o tools/sim1_cold_start.csv
cat cold_start.csv
