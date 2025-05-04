All whole music files (.mp3) to go in tools/music

python tools/distribute.py --peers 50 --replication 3

python tools/split.py (need to change the music file name)

python tracker.py
python peer.py <peer_number>




Docker:

docker-compose down --remove-orphans

docker-compose build

docker-compose up -d tracker

./docker-run-peers.sh

