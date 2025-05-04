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
python tools/distribute.py -n 50 -r 3
docker-compose down --remove-orphans
docker-compose build
./docker-run-peers.sh  
python tools/sim_cold_start.py -f comf_numb.mp3 -n 50 -o tools/sim_csv/sim_cold_start.csv
cat cold_start.csv

# Churn :
python tools/sim_churn.py -n 50 -r 5 -d 60 -o tools/sim_csv/churn5.csv 

# Peer starvation : 
python tools/distribute_starvation_all.py --peers 50 --seed 1

# Partial distribution:
python tools/distribute_partial.py --peers 50 --replication 3 --missing 0.3
