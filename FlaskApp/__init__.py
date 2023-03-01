from flask import Flask, request, send_file
import requests
import zipfile
import re
import os
import tempfile
# Always use relative import for custom module
from .package.module import MODULE_VALUE
tempFilePath = tempfile.gettempdir()
app = Flask(__name__)

@app.route("/")
def index():
    return (
        "Try /download and pass the terraform resource markdown raw link.\n"
        "Try /module for module import guidance"
    )


def create_readme_file(url):
  # Download the contents of the URL
  r = requests.get(url)
  content = r.text
  match = re.search(r'\#\s+(\w+)', content)
  if match:
    resource_fullname = match.group(1)
    resource_name = resource_fullname.split('_')[1].lower()

  # Extract the readmd content reference section
  pattern = r'---(.*?)## Argument(.*?)'
  readme_section = re.search(pattern, content, re.DOTALL)
  if readme_section:
    readme_section = readme_section.group(1)
  # Write the readmd content to a file
  with open(tempFilePath+'/read.md', 'w') as f:
    f.write(readme_section)
    f.write('\n')
    f.write(f'<!-- BEGIN_TF_DOCS --> \n')
    f.write(f'{{ .Content }} \n')
    f.write(f'<!-- END_TF_DOCS --> \n')

def create_output_variables_file(url):
  # Download the contents of the URL
  r = requests.get(url)
  content = r.text
  match = re.search(r'\#\s+(\w+)', content)
  if match:
    resource_fullname = match.group(1)
    resource_name = resource_fullname.split('_')[1].lower()

  # Extract the arguments reference section
  pattern = r'## Attributes Reference(.*?)##'
  outputs_section = re.search(pattern, content, re.DOTALL).group(1)

  # Pattern to extract non block variables section
  out_section = ""
  pattern = r'([\s\S]*?)---'
  outputs_nblock = re.search(pattern, outputs_section, re.DOTALL)
  if outputs_nblock:
    out_section = outputs_nblock.group(1)
  else:
    out_section = outputs_section

  # Extract the output variables
  pattern = r'\* \`(\w+)\`(.*?)\n'
  output_variables = re.findall(pattern, out_section, re.DOTALL)

# Extract block variables
  block_variables_pattern = r'---(.*?)---'
  block_variables_matches = re.finditer(block_variables_pattern, outputs_section, re.DOTALL)

  block_output_variables = []
  for match in block_variables_matches:
    block_var = match.group(1)
    name_pattern = r'`(\w+)`'
    var_pattern = r'\* `(\w+)`(.*?)\n'
    name_match = re.search(name_pattern, block_var)
    if name_match:
      name = name_match.group(1)
      block_vars = re.findall(var_pattern, block_var)
      for allvars in block_vars:
        block_var_name = allvars[0]
        block_var_description = allvars[1].strip().replace('- ', '')
        block_output_variables.append((name, block_var_description, block_var_name))

  # Write the output variables to a file
  with open(tempFilePath+'/outputs.tf', 'w') as f:
    for variable in output_variables:
      name = variable[0]
      description = variable[1].strip()
      f.write(f'output "{name}" {{\n')
      f.write(f'  value = {resource_fullname}.{resource_name}.{name}\n')
      f.write(f'  description = "{description}"\n')
      f.write('}\n')
    for variable in block_output_variables:
      name = variable[0]
      description = variable[1].strip()
      output_var = variable[2].strip()
      f.write(f'output "{name}" {{\n')
      f.write(f'  value = {resource_fullname}.{resource_name}.{name}.{output_var}\n')
      f.write(f'  description = "{description}"\n')
      f.write('}\n')

def create_variables_file(url):
  # Download the contents of the URL
  r = requests.get(url)
  content = r.text

  # Extract the arguments reference section
  pattern = r'## Argument(.*?)##'
  arguments_section = re.search(pattern, content, re.DOTALL).group(1)

  # Pattern to extract non block variables section
  pattern = r'([\s\S]*?)---'
  variables_section = re.search(pattern, arguments_section, re.DOTALL).group(1)

  # Extract the variables
  pattern = r'\* `(\w+)`(.*?)\n'
  variables = re.findall(pattern, variables_section, re.DOTALL)

  # Extract block variables
  block_variables_pattern = r'---(.*?)---'
  block_variables_matches = re.finditer(block_variables_pattern, arguments_section, re.DOTALL)

  # Pattern to extract block variables section
  #block_vars_match_pattern = r'([\s\S]*?)## Attributes Reference'
  #block_variables_section = re.search(block_vars_match_pattern, block_variables_matches, re.DOTALL).group(1)

  block_variables = []
  for match in block_variables_matches:
    block_var = match.group(1)
    name_pattern = r'`(\w+)`'
    var_pattern = r'\* `(\w+)`(.*?)\n'
    name_match = re.search(name_pattern, block_var)
    if name_match:
      name = name_match.group(1)
      block_vars = re.findall(var_pattern, block_var)
      all_vars = ""
      type_vars = "type = object({ \n"
      default_vars = "default = { \n"
      for allvars in block_vars:
        block_var_name = allvars[0]
        block_var_description = allvars[1].strip().replace('- ', '')
        type_vars += f'   {block_var_name}= string,  \n'
        default_vars += f'    {block_var_name} = "" \n //{block_var_description} \n\n'
      blank = ""
      type_vars = blank.join(type_vars.rsplit(',', 1))
      type_vars += '})\n'
      default_vars += '}\n'
      all_vars = type_vars + "\n" + default_vars
      block_variables.append((name, all_vars))

  # Write the variables to a file
  with open(tempFilePath+'/variables.tf', 'w') as f:
    for variable in variables:
      name = variable[0]
      description = variable[1].strip()
      f.write(f'variable "{name}" {{\n')
      f.write(f'  description = "{description}"\n')
      f.write('}\n')
    for variable in block_variables:
      name = variable[0]
      block = variable[1]
      f.write(f'variable "{name}" {{\n')
      f.write(f'{block}\n')
      f.write('}\n')

def create_locals_file(url):
  # Download the contents of the URL
  r = requests.get(url)
  content = r.text
  match = re.search(r'\#\s+(\w+)', content)
  if match:
    resource_fullname = match.group(1)
    resource_name = resource_fullname.split('_')[1].lower()
  
  locals = """
  #Standard tags, naming convention and shared variables to load and use in the module

  #shared variables 
  #module "shared_vars" {
  #  source      = "git::https://dev.azure.com/company/company-terraform/_git/azure-shared-vars?ref=v1"
  #  location    = var.location
  #  environment = var.environment
  #}


  locals {
    common_tags = merge(local.standard_tags, var.additional_tags)
    standard_tags = {
      "ApplicationName"    = var.app_name
      "Project"     = var.project
      "Description"     = var.description
      "Environment"   = var.environment
      "OwnerEmail"       = var.owner_email
      "AlertEmail"  = var.alert_email
      "External"  = var.external
    }
  """
  locals += "#resource naming convention \n"
  locals += 'storage_name = "${var.app_name}-${var.environment}-${var.location}-'+f"{resource_name}"+'-${var.index}"'
  
  # Write the variables to a file
  with open(tempFilePath+'/locals.tf', 'w') as f:
    f.write(locals)

def create_resource_file(url):
  global resourceN
  # Download the contents of the URL
  r = requests.get(url)
  content = r.text
  match = re.search(r'\#\s+(\w+)', content)
  if match:
    resource_fullname = match.group(1)
    #drop azurerm_ from resource_fullname
    resource_name = re.sub(r'azurerm_', '', resource_fullname) 
    #resource_name = resource_fullname.split('_')[1].lower()

  # Extract the readmd content reference section
  pattern = r'```hcl(.*?)```'
  resources_section = re.search(pattern, content, re.DOTALL).group(1)
  # Write the readmd content to a file
  with open(f"{tempFilePath}/{resource_name}.tf", 'w') as f:
    f.write(resources_section)
    f.write('\n')
    #return resource_fullname without "azurerm_"
    return resource_name


def zip_text_files(resource_name):
    # delete any existing zip files
    for file in os.listdir():
        if file.endswith(".zip"):
            os.remove(file)

    # zip the text files
    with zipfile.ZipFile(tempFilePath+"/"+resource_name + ".zip", "w") as zip:
        zip.write(tempFilePath+"/read.md")
        zip.write(tempFilePath+"/outputs.tf")
        zip.write(tempFilePath+"/variables.tf")
        zip.write(tempFilePath+"/locals.tf")
        zip.write(f"{tempFilePath}/{resource_name}.tf")
        # delete all tf module files
        os.remove(tempFilePath+"/read.md")
        os.remove(tempFilePath+"/outputs.tf")
        os.remove(tempFilePath+"/variables.tf")
        os.remove(tempFilePath+"/locals.tf")
        os.remove(f"{tempFilePath}/{resource_name}.tf")
        #os.remove("download")


@app.route('/download', methods=['POST'])
def download_zip():
    # get the 'url' from the request body
    if request.form:
        url = request.form['url']
    elif request.get_json():
        data = request.get_json()
        url = data['url']
    # create the text files
    create_readme_file(url)
    create_output_variables_file(url)
    create_variables_file(url)
    create_locals_file(url)
    resource_name = create_resource_file(url)
    zip_text_files(resource_name)
    return send_file(tempFilePath+"/"+resource_name+".zip", as_attachment=True)

@app.route('/gui', methods=['GET'])
def gui():
    return '''
    <head>
    <style>
        body{
            background-color: black;
                }
            </style>
            <link href="https://unpkg.com/tailwindcss@^1.0/dist/tailwind.min.css" rel="stylesheet">
        </head>
        <div class="flex flex-col justify-center min-h-screen py-6 overflow-hidden bg-black">
        <div class="flex justify-center bg-black"> 
            <img src="https://tech.feedforce.jp/images/2015/07/terraform-logo.png" alt="" class="max-w-none" width="500"/>
        </div> 
        <div class="flex justify-center text-center text-white">
        <h1 class="text-2xl text-transparent transition duration-500 transform bg-clip-text bg-gradient-to-r from-teal-400 to-blue-500 translate-z-10 hover:scale-125">Module Template Starter</h1>
        </div>
        <div class="relative px-6 pt-10 pb-8 bg-black shadow-xl ring-1 ring-gray-900/5 sm:mx-auto sm:max-w-lg sm:rounded-lg sm:px-10">
            <div class="max-w-md mx-auto">
            <div class="divide-y divide-gray-300/50">
                <div class="py-8 space-y-6 text-base leading-7 text-gray-600">
                <form action="/download" method="POST" class="p-6 m-4 bg-black rounded shadow" style="margin: 0 auto;">
                    <label>Enter terraform resource markdown link </label>
                    <input type="text" name="url" bg-black rounded shadow>
                    <input type="submit" value="Submit" class="px-4 py-2 font-bold text-white bg-blue-500 rounded hover:bg-blue-700">
                </form>
                </div>
            </div>
            </div>
        </div>
        </div>
    
    '''

@app.route("/module")
def module():
    return f"loaded from FlaskApp.package.module = {MODULE_VALUE}"

if __name__ == "__main__":
    app.run()