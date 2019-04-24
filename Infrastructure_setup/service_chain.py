"""
University of Colorado Boulder

Project Team:
Dashmeet Singh Anand          Email: daan9363@colorado.edu
Hariharakumar Narasimhakumar  Email: hana88349@colorado.edu
Rohit Dilip Kulkarni          Email: roku1038@colorado.edu
Sarang Ninale                 Email: sani1268@colorado.edu

Network Diagram:
Iperf3 Client --> Openstack Server --> Iperf3 Server
	[c]		[OS]		[S]
Software Dependencies:
1. Iperf3 [c][s]
2. Ping	[c]
3. OpenStack Gnnochi [os]
4. Node Metric - Promethius [os]

Run Procedure:
1. Start the Iperf3 Server.
2. Ensure ICMP, TCP and UDP across the service chain.
3. Ensure traffic rules hold for 1Hr or test_time specified. (Specially in firewalls)
4. Start the test.

Global Variables:
testing_time:		Time for testing the service chain and collection of metrics.
sleep_time: 		Time between each test for cool down.
iperf_server:		Address for the iperf server.
openstack_server: 	Address for the openstack deployed server. 
server_promethius:	Promethius datasource for node_exporter metrics.
Keystone:		For collecting Gnnochi metrics.

Arguments required:
Name: 	
	Test name for storing the results.
-b --baseline:
	Test the baseline parameters of the server for previous 1 Hr.
-t --tcp:
	Sends tcp traffic for testing_time. 
-s --stream:
	Send tcp with 100 parallel stream for testing_time.
-u --udp:
	Sends UDP packets for testing_time.
-l --latency:
	Checks the latency for the across the client and server.
-a --all:
	Test Latency -> TCP -> TCP-Stream -> UDP of network.
-w --wait:
	Sleeps for 1 Hr.
"""
import requests
import time
from prettytable import PrettyTable
import re
import subprocess
import datetime
import argparse
import os
import sys

from keystoneauth1.identity import v3
from keystoneauth1 import session
from keystoneclient.v3 import client
from gnocchiclient.v1 import client as gnocchi_client
from novaclient import client as nova_client


def request_calls(url):
	"""
	Requesting different parameters from HTTP calls		
	url: [string] : poinitng to the promethius server.
	Return:
		data_points: returns list of data metrics.
	"""
	r=requests.get(url)
	r=r.json()
	data_values=r['data']['result'][0]['values']
	data_points=[]
	for ele in data_values:
		data_points.append(float(ele[1]))
	return(data_points)

def calc_min_max_avg(data_points):
	"""
	Calculations of Maximum, Minimum and Average from a string of floats.
	data_points: [list] : float list of metric collected.
	Return:
		max_var: Maximum value of list.
		min_var: Minimum value of list.
		avg: Avergage value.
	"""
	max_var=round(max(data_points),2)
	min_var=round(min(data_points),2)
	sum_var=sum(data_points)
	count=len(data_points)
	avg=round((sum_var/count),2)
	return (max_var,min_var,avg)

def server_metrics():
	"""
	Fetching metrics from promethius server.
	Return:
		srv_pt: pretty table output for the server metric collected.
	"""
	
	global server_promethius
	global start_time
	global end_time

	server = server_promethius

	srv_pt = PrettyTable()
	srv_pt.field_names = ["Parameter", "Max", "Min", "Average"]

	#cpu utilization percentage
	url=server+"api/v1/query_range?query=(((count(count(node_cpu_seconds_total%7Binstance%3D~%22localhost%3A9100%22%2Cjob%3D~%22node_exporter%22%7D)%20by%20(cpu)))%20-%20avg(sum%20by%20(mode)(irate(node_cpu_seconds_total%7Bmode%3D'idle'%2Cinstance%3D~%22localhost%3A9100%22%2Cjob%3D~%22node_exporter%22%7D%5B5m%5D))))%20*%20100)%20%2F%20count(count(node_cpu_seconds_total%7Binstance%3D~%22localhost%3A9100%22%2Cjob%3D~%22node_exporter%22%7D)%20by%20(cpu))&start="+str(start_time)+"&end="+str(end_time)+"&step=5&timeout=60s"
	data_points=request_calls(url)
	max_var,min_var,avg=calc_min_max_avg(data_points)
	srv_pt.add_row(['cpu_utilization [%]',max_var,min_var,avg])

	#ram utilization percentage
	url=server+"api/v1/query_range?query=100%20-%20((node_memory_MemAvailable_bytes%7Binstance%3D~%22localhost%3A9100%22%2Cjob%3D~%22node_exporter%22%7D%20*%20100)%20%2F%20node_memory_MemTotal_bytes%7Binstance%3D~%22localhost%3A9100%22%2Cjob%3D~%22node_exporter%22%7D)&start="+str(start_time)+"&end="+str(end_time)+"&step=5&timeout=60s"
	data_points=request_calls(url)
	max_var,min_var,avg=calc_min_max_avg(data_points)
	srv_pt.add_row(['ram_utilization [%]',max_var,min_var,avg])

	#Load percentage 1 m
	url=server+"api/v1/query_range?query=avg(node_load1%7Binstance%3D~%22localhost%3A9100%22%2Cjob%3D~%22node_exporter%22%7D)%20%2F%20%20count(count(node_cpu_seconds_total%7Binstance%3D~%22localhost%3A9100%22%2Cjob%3D~%22node_exporter%22%7D)%20by%20(cpu))%20*%20100&start="+str(start_time)+"&end="+str(end_time)+"&step=5&timeout=60s"
	data_points=request_calls(url)
	max_var,min_var,avg=calc_min_max_avg(data_points)
	srv_pt.add_row(['System_Load [%]',max_var,min_var,avg])

	#Load percentage 5 m
	url=server+"api/v1/query_range?query=avg(node_load5%7Binstance%3D~%22localhost%3A9100%22%2Cjob%3D~%22node_exporter%22%7D)%20%2F%20%20count(count(node_cpu_seconds_total%7Binstance%3D~%22localhost%3A9100%22%2Cjob%3D~%22node_exporter%22%7D)%20by%20(cpu))%20*%20100&start="+str(start_time)+"&end="+str(end_time)+"&step=5&timeout=60s"
	data_points=request_calls(url)
	max_var,min_var,avg=calc_min_max_avg(data_points)
	srv_pt.add_row(['System_Load 5 m [%]',max_var,min_var,avg])

	return (srv_pt)

def latency_testing():
	"""
	Perform RTT ping between the server and client.
	Writes data on file.
	Return:
		True/False: [boolean]: Test completed.  
	"""
	global start_time
	global end_time
	global testing_time
	global iperf_server
	print ("Traffic Latency Test")
	perf_pt = PrettyTable()
    	perf_pt.field_names = ["Traffic Deatils","Parameter", "Max", "Min", "Average"]
	start_time=time.time()
	data = subprocess.check_output(['ping', '-c', '10', iperf_server])
	end_time=time.time()
    	val = re.search('([\d]*\.[\d]*)/([\d]*\.[\d]*)/([\d]*\.[\d]*)/([\d]*\.[\d]*)', data)
    	min_var = float(val.group(1))
    	avg = float(val.group(2))
    	max_var = float(val.group(3))
    	perf_pt.add_row(['Ping test','Latency [ms]',max_var,min_var,avg])
    	write_data("Traffic Latency Test",str(perf_pt))
	return (True)
	
def tcp_testing():
	"""
	Performs Iperf3 TCP testing.
	Writes data on a file. 
	"""
	global start_time
	global end_time
	global testing_time
	global iperf_server
	print ("Iperf TCP testing")
	perf_pt = PrettyTable()
    	perf_pt.field_names = ["Traffic Deatils","Parameter", "Max", "Min", "Average"]
    	start_time=time.time()
	command="iperf3 -c "+iperf_server+" -t "+testing_time+" -f m -V"
  	p = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
	(data,err)=p.communicate()
	p_status=p.wait()
  	end_time=time.time()
   	fetch_metrics(addpfix="TCP")
	traffic_details = test_details(data)
	max_var,min_var,avg = calc_min_max_avg(bandwidth_details_tcp(data))
	perf_pt.add_row([traffic_details,'Throughput [Mbits/Sec]',max_var,min_var,avg])
	write_data("Iperf TCP testing",str(perf_pt))
	
def stream_testing():
	"""
	Performs Iperf3 TCP stream testing with 100 parallel connections.
	Writes data on a file. 
	"""
	global start_time
	global end_time
	global testing_time
	global iperf_server
	print ("Iperf TCP-Stream Testing")
	perf_pt = PrettyTable()
    	perf_pt.field_names = ["Traffic Deatils","Parameter", "Max", "Min", "Average"]
    	start_time=time.time()
        command="iperf3 -c "+iperf_server+" -t "+testing_time+" -P 100 -f m -V"
        p = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
        (data,err)=p.communicate()
        p_status=p.wait()
    	end_time=time.time()
    	fetch_metrics(addpfix="TCP-Stream")
	traffic_details = test_details(data)
	max_var,min_var,avg = calc_min_max_avg(bandwidth_details_tcp(data))
	perf_pt.add_row([traffic_details,'Throughput [Mbits/Sec]',max_var,min_var,avg])
	write_data("Iperf TCP testing",str(perf_pt))
	return (True)
	
def udp_testing():
	"""
	Performs Iperf3 UDP testing.
	Writes data on a file. 
	"""
	global start_time
	global end_time
	global testing_time
	global iperf_server
	print ("Iperf UDP testing")
	perf_pt = PrettyTable()
    	perf_pt.field_names = ["Traffic Deatils","Parameter", "Max", "Min", "Average","Datagrams Loss %"]
    	udp_bw="1G"
 	start_time=time.time()   
        command="iperf3 -c "+iperf_server+" -t "+testing_time+" -u -b "+udp_bw+" -f m -V"
        p = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
        (data,err)=p.communicate()
        p_status=p.wait()
	print (data)
	print (err)
	end_time=time.time()
	fetch_metrics(addpfix="UDP")
	traffic_details = test_details(data)+"\n Bandwidth Set: "+udp_bw
    	max_var,min_var,avg = calc_min_max_avg(bandwidth_details_udp(data))
	loss_udp=(loss_summary(data))
    	perf_pt.add_row([traffic_details,'Throughput [Mbits/Sec]',max_var,min_var,avg,loss_udp])
	write_data("Iperf UDP testing",str(perf_pt))
	return (True)

def test_details(data):
	"""
	Collects testing detsils from output.
	data: [string] input from iperf3 tests of TCP and TCP streams.
	Return:
		traffic_detail: [string] : start time, end time, protocol and streams.
	"""
	global start_time
	global end_time	
	protocol = re.findall(r'Starting Test: protocol: (.*), \d{1,3} streams',data)[0]
	streams = re.findall(r'Starting Test: protocol: .*, (.*) streams,',data)[0]
	# convert time formats
	test_start_time = time.strftime('%d-%m-%Y %H:%M:%S', time.localtime(start_time))
	test_end_time = time.strftime('%d-%m-%Y %H:%M:%S', time.localtime(end_time))

	traffic_details=("Test start time: {}\nTest  end  time: {}\nProtocols: {}\nStreams: {}".format(test_start_time,test_end_time,protocol,streams))

	return (traffic_details)

def bandwidth_details_tcp(data):
	"""
	Collects bandwidth data from tcp data. 
	data: [string] input from iperf3 tests of TCP and TCP streams.
	Return:
		bandwidth: [list] : floating values of the BW in test output.
	"""
	bandwidth=re.findall(r'  (\d{1,3}.\d{1,3}) Mbits/sec .*Bytes',data)
	if bandwidth != []:
	    for i,val in enumerate(bandwidth):
		bandwidth[i]=round(float(val),2)
	else:
	    bandwidth=[0]
	
	return (bandwidth)

def bandwidth_details_udp(data):
	"""
	Collects bandwidth details of UDP data.
	data: [string] input from iperf3 tests of UDP.
	Return:
		bandwidth: [list] : floating values of the BW in test output.
	"""
	bandwidth=re.findall(r'  (\d{1,3}.\d{1,3}) Mbits/sec',data)
	if bandwidth != []:
	    del bandwidth[-1:] #deletes for summary lines
	    for i,val in enumerate(bandwidth):
		bandwidth[i]=round(float(val),2)
	else:
	    bandwidth=[0]
	
	return (bandwidth)

def loss_summary(data):
	"""
	Collectes  the loss in UDP from the test results. 
	data: [string] input from iperf3 tests of UDP.
	Return:
		loss: str : % value of datagram loss in UDP.
	"""
	loss = re.findall(r'\((.*?)\)',data)[0]
	return (loss)

def gnnochi_matrics():
	"""
	Collects Gnnochi metrics from OpenStack servers.
	Return:
		output_tables: str : Pretty table output of gnnochi metrics collected.
	"""
	global keystone
	global sess
	global instance_db
	global start_time
	global end_time

	gnocchi = gnocchi_client.Client(session=sess)

	metrics_fetch=['cpu_util',
			'disk.usage',
			'disk.allocation',
			'disk.root.size',
			'disk.capacity',
			'vcpus',
			'memory',
			'disk.ephemeral.size']

	output_tables=""
	for instance in instance_db.keys():
		output_tables += ("------------ INSTANCE : {} ------------\n".format(instance))
		g_pt = PrettyTable()
		g_pt.field_names = ["Metric","Maximum","Minimum","Average"]
		for met in metrics_fetch:
			val_collection=[]
			list_g=gnocchi.metric.get_measures(metric=met,
							start=start_time,
							stop=end_time,
							resource_id=instance_db[instance])
			for ele in list_g:
				val_collection.append(round(float(ele[2]),2))

			if val_collection != []:
				min_val=min(val_collection)
				max_val=max(val_collection)
				sum_val=sum(val_collection)
				avg_val=round(sum_val/len(val_collection),2)
			else:
				min_val = max_val = avg_val ="Error"

			g_pt.add_row([met,max_val,min_val,avg_val])
		output_tables += str(g_pt) +'\n'
	return (output_tables)

def nova_list():
	"""
	Collects the complete list of VNF IDs deployed in the OpenStack environment.
	Return:
		instance_db: [dictionary]: VNF name and the ID is updated in global variable. 
	"""
	global instance_db
	nova = nova_client.Client(2, session=sess)
	#print (nova.servers.list())
	for server in nova.servers.list():
		instance_db[server.name]=server.id

def fetch_metrics(addpfix=""):
	"""
	Synchronizing the complete metric collections.
	writes data on files for logging. 
	addpfix: [string] adds the prefix provided by the user.
	"""
	global server_promethius
	global auth
	global sess
	global keystone
	
	global instance_db

	global pfix

	global openstack_server

	prefix=str(pfix)+"|"+str(addpfix)
	
	#HOST METRICS
	
	srv_pt=server_metrics()
	write_data(prefix+" Server Metric",str(srv_pt))

	#GNNOCHI METRICS
	auth = v3.Password(auth_url='http://'+openstack_server+'/identity/v3',
						username='admin',
						password='qwe123',
						project_name='admin',
						user_domain_id="default",
						project_domain_id="default")
	sess = session.Session(auth=auth)
	keystone = client.Client(session=sess)

	nova_list()
	if instance_db != {}:
		g_pt_all=gnnochi_matrics()
		write_data(prefix+" Gnnochi Metric",str(g_pt_all))
	else:
		write_data(prefix+" Gnnochi Metric","Error")

def sleep_monitor(sleep_time):
	"""
	Interactive screen for monitoring the sleep times 
	sleep_time: [int]: time values in second.
	"""
	for remaining in range(sleep_time, 0, -1):
                sys.stdout.write("\r")
                sys.stdout.write("Cooldown countdown: {} ".format(remaining))
                sys.stdout.flush()
                time.sleep(1)
        return()


def write_data(heading,data):
	"""
	Function to write the  test data onto a file. 
	heading: [str] prefix to be added to file name.
	data: [str] data to be written.
	"""
	global test_name
	global start_time
	global end_time

	with open(test_name+".output",'aw+') as out_file:
		out_file.write("\nCurrent time: {}\n".format(datetime.datetime.now()))
		out_file.write("Test name: {} | Heading: {}\n".format(test_name,heading))
		out_file.write("Start time:{} | End time:{}\n".format(time.strftime('%d-%m-%Y %H:%M:%S', time.localtime(start_time)),
									time.strftime('%d-%m-%Y %H:%M:%S', time.localtime(end_time))))
		out_file.write("Results: \n")
		out_file.write(data)
		out_file.write("\n")
		out_file.write("*"*50)
	print (data+"\n")
	return (True)

def all_test():
	"""
	Synchronizing the complete test when --all is given.
	"""
	global test_name
	global sleep_time
	global start_time
	global end_time
	global pfix

	print ("STARTING ALL TEST")

	#Latency
	test_name="all_latency_"+test_name
	pfix="ALL-TRAFFIC-LATENCY"
	latency_testing()
	sleep_monitor(sleep_time)
	
	#TCP
	test_name="all_tcp_"+test_name
	pfix="ALL-TRAFFIC-TCP"
	tcp_testing()
	start_time=time.time()
	sleep_monitor(sleep_time)
	end_time=time.time()
	fetch_metrics(addpfix="AFTER TCP")
	
	#TCP-Stream
	test_name="all_tcpstream_"+test_name
	pfix="ALL-TRAFFIC-TCP-STREAM"
	stream_testing()
	start_time=time.time()
	sleep_monitor(sleep_time)
	end_time=time.time()
	fetch_metrics(addpfix="AFTER TCP-STREAM")
	
	#UDP
	test_name="all_udp_"+test_name
	pfix="ALL-TRAFFIC-UDP"
	udp_testing()
	

if __name__ == "__main__":
	#ARGPARSE
	main_start=time.time()
	parser=argparse.ArgumentParser()
	parser.add_argument("name", help="identifier for test to be written to the file")
	parser.add_argument("-b","--baseline",help="Does not send Iperf traffic",action="store_true")
	parser.add_argument("-t","--tcp",help="Sends TCP traffic",action="store_true")
	parser.add_argument("-s","--stream",help="Sends TCP traffic with 100 Parallel streams",action="store_true")
	parser.add_argument("-u","--udp",help="Sends UDP traffic",action="store_true")
	parser.add_argument("-l","--latency",help="Test Latency of network",action="store_true")
	parser.add_argument("-a","--all",help="Test Latency -> TCP -> TCP-Stream -> UDP of network",action="store_true")
	parser.add_argument("-w","--wait",help="wait for 1 hr before starting tests",action="store_true")
	args = parser.parse_args()

	#global parameters
	iperf_server='2.2.2.2'
	openstack_server="172.16.218.20"
	
	server_promethius="http://"+openstack_server+":9090/"
	auth=""
	sess=""
	keystone=""

	instance_db={}

	test_name=args.name
	
	testing_time='3600'
	sleep_time=900

	#IPERF AND BASELINE
	start_time=""
	end_time=""
	if args.wait:
		print ("Sleeping for 1 Hr")
		sleep_monitor(3600)
	if args.baseline:
		print ("!!! Fetching Baseline values !!!")
		end_time=time.time()
		start_time=end_time-3600
                pfix="BASELINE"
                fetch_metrics()
	if args.tcp:
		pfix="TRAFFIC-TCP"
		tcp_testing()
	if args.stream:
		pfix="TRAFFIC-STREAM"
		stream_testing()
	if args.udp:
		pfix="TRAFFIC-UDP"
		udp_testing()
	if args.latency:
		pfix="TRAFFIC-LATENCY"
		latency_testing()
	if args.all:
		all_test()

	
	main_end=time.time()
	#FIN
	wr_data=("EPOC Start time:{} | End time:{} \n".format(main_start,main_end))
	wr_data+=("Start time:{} | End time:{}".format(time.strftime('%d-%m-%Y %H:%M:%S', time.localtime(main_start)),time.strftime('%d-%m-%Y %H:%M:%S', time.localtime(main_end))))
	write_data("Timestamp",wr_data)
