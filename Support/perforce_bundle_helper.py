import os, shlex, subprocess
from P4 import P4, P4Exception

p4 = None

def connect_to_p4():
	global p4
	
	if p4 is None:
		p4 = P4()
		
	if not p4.connected():
		try:
			p4.connect()
		except P4Exception as p4_error:
			print(p4_error)
			
	return p4


def get_textmate_file_list():
	# shlex.split parses the bash argument string into a list
	return shlex.split(os.environ['TM_SELECTED_FILES']) if os.environ.has_key('TM_SELECTED_FILES') \
		else [os.environ['TM_FILEPATH']] if os.environ.has_key('TM_FILEPATH') \
		else []


def get_files_relative_to_p4_workspace(file_list):
	'''
	Returns a new list that only contains files from file_list that are inside
	the P4 current workspace, with paths relative to it.
	'''
	
	connect_to_p4()
	
	if p4 and p4.connected():
		p4_info = p4.run('info')[0]
		p4_workspace = p4_info['clientRoot'] + '/'
		
		p4.cwd = p4_workspace
		os.chdir(p4_workspace)
		
		return [file.replace(p4_workspace, '') for file in file_list if file.startswith(p4_workspace)]
		

def prepare_file_list_for_p4(file_and_directory_list):
	'''
	Returns a new list that
	 - adds /... to the ends of directory paths
	 - filters out files that are children of a supplied directory
	'''	

	file_list = []
	directory_list = []

	for file_or_directory in file_and_directory_list:
		if os.path.isdir(file_or_directory):
			directory_list.append(file_or_directory)
		else:
			file_list.append(file_or_directory)

	result = [directory + '/...' for directory in directory_list]

	for file in file_list:
		file_in_directory = False

		for directory in directory_list:
			if file.startswith(directory):
				file_in_directory = True
				break

		if not file_in_directory:
			result.append(file)

	return result


def get_all_files_in_file_list(file_list):
	result = []
	
	for file in file_list:
		if os.path.isdir(file):
			result.extend(get_files_under_directory(file))
		else:
			result.append(file)
			
	# set returns an iterable that ensures all its keys are unique
	return set(result)


def get_files_under_directory(root_path):
	files = []

	for walk_result_tuple in os.walk(root_path):
		directory_path = walk_result_tuple[0]
		child_file_list = walk_result_tuple[2]
		
		for file_name in child_file_list:
			if not file_name.startswith('.'):
				files.append(os.path.join(directory_path, file_name))
	
	return files


def run_p4_command_on_selected_textmate_files(*args, **kwargs):
	# This method should have the same signature as run_p4_command, but the
	# only way I could get the passthrough to work was with *args and **kwargs.
	#
	# If I wasn't in a rush, I'd figure out the right way to pass through named
	# parameters.  In the mean time, I'll just name them here:
	command = args[0]


	traverse_directories_by_hand_for_these_commands = ['add']
	
	try:
		file_list = get_files_relative_to_p4_workspace(
						get_textmate_file_list()
					)
		
		# if get_files_relative_to_p4_workspace returns None, we're not probably connected to P4
		assert file_list is not None
					
		if command in traverse_directories_by_hand_for_these_commands:
			file_list = get_all_files_in_file_list(file_list)
		else:
			file_list = prepare_file_list_for_p4(file_list)
		
	except AssertionError:
		return ["Your command was not executed because of an error."]
	
	if not file_list:
		return ["These files are not in your P4 workspace."]
		
	else:
		kwargs['file_list'] = file_list
		return run_p4_command(*args, **kwargs)
		

def run_p4_command(command, file_list = [], fallback_command = None, fallback_silently = True):
	try:
		connect_to_p4()
					
	except AssertionError:
		return ["Your command was not executed because of an error."]

	p4_response = []
	
	# This makes P4's output human-readible instead of dict-y
	p4.tagged = False
	
	def run_command(command, fallback_command = None):
		p4_response = []

		'''
		When you submit or shelve a changeset without a hardcoded
		description, p4 will give you the opportunity to create one in
		the app specified by $EDITOR.
		
		'mate -w' spawns TextMate and tells it to wait until you close
		the window to send its contents to stdin.
		'''
		if not os.environ.has_key('EDITOR'):
			os.environ['EDITOR'] = os.environ['TM_SUPPORT_PATH'] + '/bin/mate -w'
		
		# If someone passes arguments in along with command, parse them correctly
		p4_args = shlex.split(command)
		command = p4_args[0]
		p4_args = p4_args[1:]
		
		if file_list:
			p4_args.extend(file_list)
					
		try:
			p4_response = p4.run(command, p4_args)
			p4.disconnect()
			
			return p4_response
			
		except P4Exception:
			if fallback_command: 
				p4_response = run_command(fallback_command)
			
			elif not fallback_silently or (fallback_silently and not fallback_command):
				if p4.warnings:
					print('<h2>Warnings:</h2>')
					for message in p4.warnings:
						print(message)

				if p4.errors:
					print('<h2>Errors:</h2>')
					for message in p4.errors:
						print(message)
			
			return p4_response
	
	return run_command(command, fallback_command)


def stdout_to_html(lines, line_delimiter = '\n'):
	html = line_delimiter.join(lines)
	html = html.replace('&', '&amp;').replace('<', '&lt;')
	return '<pre>' + html + '</pre>'
	
	
	
# force TM to refresh current file and project drawer
def rescan_project():
	subprocess.check_output('''osascript &>/dev/null \
		-e 'tell app "SystemUIServer" to activate' \
		-e 'tell app "TextMate" to activate' &''',
		shell = True
	)
