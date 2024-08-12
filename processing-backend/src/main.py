from langchain_community.graphs import Neo4jGraph
from src.shared.constants import BUCKET_UPLOAD, PROJECT_ID
from src.shared.schema_extraction import schema_extraction_from_text
from dotenv import load_dotenv
from datetime import datetime
import logging
from src.create_chunks import CreateChunksofDocument
from src.graphDB_dataAccess import graphDBdataAccess
from src.document_sources.local_file import get_documents_from_file_by_path
from src.entities.source_node import sourceNode
from src.llm import get_graph_from_llm
from src.document_sources.gcs_bucket import *
from src.document_sources.s3_bucket import *
from src.document_sources.wikipedia import *
from src.document_sources.youtube import *
from src.shared.common_fn import *
from src.make_relationships import *
from src.document_sources.web_pages import *
import re
from langchain_community.document_loaders import WikipediaLoader, WebBaseLoader
import warnings
from pytube import YouTube
import sys
import shutil
import urllib.parse
import json

warnings.filterwarnings("ignore")
load_dotenv()
logging.basicConfig(format='%(asctime)s - %(message)s',level='INFO')

    
def extract_graph_from_file_local_file(uri, userName, password, database, model, merged_file_path, fileName, allowedNodes, allowedRelationship):

  logging.info(f'Process file name :{fileName}')
  gcs_file_cache = os.environ.get('GCS_FILE_CACHE')
  if gcs_file_cache == 'True':
    folder_name = create_gcs_bucket_folder_name_hashed(uri, fileName)
    file_name, pages = get_documents_from_gcs( PROJECT_ID, BUCKET_UPLOAD, folder_name, fileName)
  else:
    file_name, pages, file_extension = get_documents_from_file_by_path(merged_file_path,fileName)
  if pages==None or len(pages)==0:
    raise Exception(f'File content is not available for file : {file_name}')

  return processing_source(uri, userName, password, database, model, file_name, pages, allowedNodes, allowedRelationship, True, merged_file_path)

def extract_graph_from_file_s3(uri, userName, password, database, model, source_url, aws_access_key_id, aws_secret_access_key, allowedNodes, allowedRelationship):

  if(aws_access_key_id==None or aws_secret_access_key==None):
    raise Exception('Please provide AWS access and secret keys')
  else:
    logging.info("Insert in S3 Block")
    file_name, pages = get_documents_from_s3(source_url, aws_access_key_id, aws_secret_access_key)

  if pages==None or len(pages)==0:
    raise Exception(f'File content is not available for file : {file_name}')

  return processing_source(uri, userName, password, database, model, file_name, pages, allowedNodes, allowedRelationship)

def extract_graph_from_web_page(uri, userName, password, database, model, source_url, allowedNodes, allowedRelationship):

  file_name, pages = get_documents_from_web_page(source_url)

  if pages==None or len(pages)==0:
    raise Exception(f'Content is not available for given URL : {file_name}')

  return processing_source(uri, userName, password, database, model, file_name, pages, allowedNodes, allowedRelationship)

def extract_graph_from_file_youtube(uri, userName, password, database, model, source_url, allowedNodes, allowedRelationship):
  
  file_name, pages = get_documents_from_youtube(source_url)

  if pages==None or len(pages)==0:
    raise Exception(f'Youtube transcript is not available for file : {file_name}')

  return processing_source(uri, userName, password, database, model, file_name, pages, allowedNodes, allowedRelationship)

def extract_graph_from_file_Wikipedia(uri, userName, password, database, model, wiki_query, max_sources, language, allowedNodes, allowedRelationship):

  file_name, pages = get_documents_from_Wikipedia(wiki_query, language)
  if pages==None or len(pages)==0:
    raise Exception(f'Wikipedia page is not available for file : {file_name}')

  return processing_source(uri, userName, password, database, model, file_name, pages, allowedNodes, allowedRelationship)

def extract_graph_from_file_gcs(uri, userName, password, database, model, gcs_project_id, gcs_bucket_name, gcs_bucket_folder, gcs_blob_filename, access_token, allowedNodes, allowedRelationship):

  file_name, pages = get_documents_from_gcs(gcs_project_id, gcs_bucket_name, gcs_bucket_folder, gcs_blob_filename, access_token)
  if pages==None or len(pages)==0:
    raise Exception(f'File content is not available for file : {file_name}')

  return processing_source(uri, userName, password, database, model, file_name, pages, allowedNodes, allowedRelationship)

def processing_source(uri, userName, password, database, model, file_name, pages, allowedNodes, allowedRelationship, is_uploaded_from_local=None, merged_file_path=None):
  """
   Extracts a Neo4jGraph from a PDF file based on the model.
   
   Args:
   	 uri: URI of the graph to extract
     db_name : db_name is database name to connect graph db
   	 userName: Username to use for graph creation ( if None will use username from config file )
   	 password: Password to use for graph creation ( if None will use password from config file )
   	 file: File object containing the PDF file to be used
   	 model: Type of model to use ('Diffbot'or'OpenAI GPT')
   
   Returns: 
   	 Json response to API with fileName, nodeCount, relationshipCount, processingTime, 
     status and model as attributes.
  """
  start_time = datetime.now()
  graph = create_graph_database_connection(uri, userName, password, database)
  graphDb_data_Access = graphDBdataAccess(graph)

  result = graphDb_data_Access.get_current_status_document_node(file_name)
  logging.info("Break down file into chunks")
  bad_chars = ['"', "\n", "'"]
  for i in range(0,len(pages)):
    text = pages[i].page_content
    for j in bad_chars:
      if j == '\n':
        text = text.replace(j, ' ')
      else:
        text = text.replace(j, '')
    pages[i]=Document(page_content=str(text), metadata=pages[i].metadata)
  create_chunks_obj = CreateChunksofDocument(pages, graph)
  chunks = create_chunks_obj.split_file_into_chunks()
  chunkId_chunkDoc_list = create_relation_between_chunks(graph,file_name,chunks)
  if result[0]['Status'] != 'Processing':      
    obj_source_node = sourceNode()
    status = "Processing"
    obj_source_node.file_name = file_name
    obj_source_node.status = status
    obj_source_node.total_chunks = len(chunks)
    obj_source_node.total_pages = len(pages)
    obj_source_node.model = model
    logging.info(file_name)
    logging.info(obj_source_node)
    graphDb_data_Access.update_source_node(obj_source_node)
    
    logging.info('Update the status as Processing')
    update_graph_chunk_processed = int(os.environ.get('UPDATE_GRAPH_CHUNKS_PROCESSED'))
    # selected_chunks = []
    is_cancelled_status = False
    job_status = "Completed"
    node_count = 0
    rel_count = 0
    for i in range(0, len(chunkId_chunkDoc_list), update_graph_chunk_processed):
      select_chunks_upto = i+update_graph_chunk_processed
      logging.info(f'Selected Chunks upto: {select_chunks_upto}')
      if len(chunkId_chunkDoc_list) <= select_chunks_upto:
         select_chunks_upto = len(chunkId_chunkDoc_list)
      selected_chunks = chunkId_chunkDoc_list[i:select_chunks_upto]
      result = graphDb_data_Access.get_current_status_document_node(file_name)
      is_cancelled_status = result[0]['is_cancelled']
      logging.info(f"Value of is_cancelled : {result[0]['is_cancelled']}")
      if bool(is_cancelled_status) == True:
         job_status = "Cancelled"
         logging.info('Exit from running loop of processing file')
         exit
      else:
        node_count,rel_count = processing_chunks(selected_chunks,graph,uri, userName, password, database,file_name,model,allowedNodes,allowedRelationship,node_count, rel_count)
        end_time = datetime.now()
        processed_time = end_time - start_time
        
        obj_source_node = sourceNode()
        obj_source_node.file_name = file_name
        obj_source_node.updated_at = end_time
        obj_source_node.processing_time = processed_time
        obj_source_node.node_count = node_count
        obj_source_node.processed_chunk = select_chunks_upto
        obj_source_node.relationship_count = rel_count
        graphDb_data_Access.update_source_node(obj_source_node)
    
    result = graphDb_data_Access.get_current_status_document_node(file_name)
    is_cancelled_status = result[0]['is_cancelled']
    if bool(is_cancelled_status) == True:
       logging.info(f'Is_cancelled True at the end extraction')
       job_status = 'Cancelled'
    logging.info(f'Job Status at the end : {job_status}')
    end_time = datetime.now()
    processed_time = end_time - start_time
    obj_source_node = sourceNode()
    obj_source_node.file_name = file_name
    obj_source_node.status = job_status
    obj_source_node.processing_time = processed_time

    graphDb_data_Access.update_source_node(obj_source_node)
    logging.info('Updated the nodeCount and relCount properties in Document node')
    logging.info(f'file:{file_name} extraction has been completed')


    # merged_file_path have value only when file uploaded from local
    
    if is_uploaded_from_local:
      gcs_file_cache = os.environ.get('GCS_FILE_CACHE')
      if gcs_file_cache == 'True':
        folder_name = create_gcs_bucket_folder_name_hashed(uri, file_name)
        delete_file_from_gcs(BUCKET_UPLOAD,folder_name,file_name)
      else:
        delete_uploaded_local_file(merged_file_path, file_name)  
      
    return {
        "fileName": file_name,
        "nodeCount": node_count,
        "relationshipCount": rel_count,
        "processingTime": round(processed_time.total_seconds(),2),
        "status" : job_status,
        "model" : model,
        "success_count" : 1
    }
  else:
     logging.info('File does not process because it\'s already in Processing status')

def processing_chunks(chunkId_chunkDoc_list,graph,uri, userName, password, database,file_name,model,allowedNodes,allowedRelationship, node_count, rel_count):
  #create vector index and update chunk node with embedding
  if graph is not None:
    if graph._driver._closed:
      graph = create_graph_database_connection(uri, userName, password, database)
  else:
    graph = create_graph_database_connection(uri, userName, password, database)
      
  update_embedding_create_vector_index( graph, chunkId_chunkDoc_list, file_name)
  logging.info("Get graph document list from models")
  graph_documents =  get_graph_from_llm(model, chunkId_chunkDoc_list, allowedNodes, allowedRelationship)
  cleaned_graph_documents = handle_backticks_nodes_relationship_id_type(graph_documents)
  save_graphDocuments_in_neo4j(graph, cleaned_graph_documents)
  chunks_and_graphDocuments_list = get_chunk_and_graphDocument(cleaned_graph_documents, chunkId_chunkDoc_list)
  merge_relationship_between_chunk_and_entites(graph, chunks_and_graphDocuments_list)
  # return graph_documents
  
  distinct_nodes = set()
  relations = []
  for graph_document in graph_documents:
    #get distinct nodes
    for node in graph_document.nodes:
          node_id = node.id
          node_type= node.type
          if (node_id, node_type) not in distinct_nodes:
            distinct_nodes.add((node_id, node_type))
  #get all relations
  for relation in graph_document.relationships:
        relations.append(relation.type)

  node_count += len(distinct_nodes)
  rel_count += len(relations)
  print(f'node count internal func:{node_count}')
  print(f'relation count internal func:{rel_count}')
  return node_count,rel_count


def merge_chunks_local(file_name, total_chunks, chunk_dir, merged_dir):

  if not os.path.exists(merged_dir):
      os.mkdir(merged_dir)
  logging.info(f'Merged File Path: {merged_dir}')
  merged_file_path = os.path.join(merged_dir, file_name)
  with open(merged_file_path, "wb") as write_stream:
      for i in range(1,total_chunks+1):
          chunk_file_path = os.path.join(chunk_dir, f"{file_name}_part_{i}")
          logging.info(f'Chunk File Path While Merging Parts:{chunk_file_path}')
          with open(chunk_file_path, "rb") as chunk_file:
              shutil.copyfileobj(chunk_file, write_stream)
          os.unlink(chunk_file_path)  # Delete the individual chunk file after merging
  logging.info("Chunks merged successfully and return file size")
  file_name, pages, file_extension = get_documents_from_file_by_path(merged_file_path,file_name)
  pdf_total_pages = pages[0].metadata['total_pages']
  file_size = os.path.getsize(merged_file_path)
  return pdf_total_pages,file_size
  


def upload_file(graph, model, chunk, chunk_number:int, total_chunks:int, originalname, uri, chunk_dir, merged_dir):
  
  gcs_file_cache = os.environ.get('GCS_FILE_CACHE')
  logging.info(f'gcs file cache: {gcs_file_cache}')
  
  if gcs_file_cache == 'True':
    folder_name = create_gcs_bucket_folder_name_hashed(uri,originalname)
    upload_file_to_gcs(chunk, chunk_number, originalname, BUCKET_UPLOAD, folder_name)
  else:
    if not os.path.exists(chunk_dir):
      os.mkdir(chunk_dir)
    
    chunk_file_path = os.path.join(chunk_dir, f"{originalname}_part_{chunk_number}")
    logging.info(f'Chunk File Path: {chunk_file_path}')
    
    with open(chunk_file_path, "wb") as chunk_file:
      chunk_file.write(chunk.file.read())

  if int(chunk_number) == int(total_chunks):
      # If this is the last chunk, merge all chunks into a single file
      if gcs_file_cache == 'True':
        file_size = merge_file_gcs(BUCKET_UPLOAD, originalname, folder_name, int(total_chunks))
        total_pages = 1
      else:
        total_pages, file_size = merge_chunks_local(originalname, int(total_chunks), chunk_dir, merged_dir)
      
      logging.info("File merged successfully")
      file_extension = originalname.split('.')[-1]
      obj_source_node = sourceNode()
      obj_source_node.file_name = originalname
      obj_source_node.file_type = file_extension
      obj_source_node.file_size = file_size
      obj_source_node.file_source = 'local file'
      obj_source_node.model = model
      obj_source_node.total_pages = total_pages
      obj_source_node.created_at = datetime.now()
      graphDb_data_Access = graphDBdataAccess(graph)
        
      graphDb_data_Access.create_source_node(obj_source_node)
      return {'file_size': file_size, 'total_pages': total_pages, 'file_name': originalname, 'file_extension':file_extension, 'message':f"Chunk {chunk_number}/{total_chunks} saved"}
  return f"Chunk {chunk_number}/{total_chunks} saved"

def get_labels_and_relationtypes(graph):
  query = """
          RETURN collect { 
          CALL db.labels() yield label 
          WHERE NOT label  IN ['_Bloom_Perspective_'] 
          AND NOT label STARTS WITH ('__') 
          AND NOT label ENDS WITH('__')
          return label order by label limit 100 } as labels, 
          collect { 
          CALL db.relationshipTypes() yield relationshipType  as type 
          WHERE NOT type  IN ['_Bloom_Perspective_']
          AND NOT type STARTS WITH ('__') 
          AND NOT type ENDS WITH('__')
          return type order by type LIMIT 100 } as relationshipTypes
          """
  graphDb_data_Access = graphDBdataAccess(graph)
  result = graphDb_data_Access.execute_query(query)
  if result is None:
     result=[]
  return result

def manually_cancelled_job(graph, filenames, source_types, merged_dir, uri):
  
  filename_list= list(map(str.strip, json.loads(filenames)))
  source_types_list= list(map(str.strip, json.loads(source_types)))
  gcs_file_cache = os.environ.get('GCS_FILE_CACHE')
  
  for (file_name,source_type) in zip(filename_list, source_types_list):
      obj_source_node = sourceNode()
      obj_source_node.file_name = file_name
      obj_source_node.is_cancelled = True
      obj_source_node.status = 'Cancelled'
      obj_source_node.updated_at = datetime.now()
      graphDb_data_Access = graphDBdataAccess(graph)
      graphDb_data_Access.update_source_node(obj_source_node)
      obj_source_node = None
      merged_file_path = os.path.join(merged_dir, file_name)
      if source_type == 'local file' and gcs_file_cache == 'True':
          folder_name = create_gcs_bucket_folder_name_hashed(uri, file_name)
          delete_file_from_gcs(BUCKET_UPLOAD,folder_name,file_name)
      else:
        logging.info(f'Deleted File Path: {merged_file_path} and Deleted File Name : {file_name}')
        delete_uploaded_local_file(merged_file_path,file_name)
  return "Cancelled the processing job successfully"

def populate_graph_schema_from_text(text, model, is_schema_description_cheked):
  """_summary_

  Args:
      graph (Neo4Graph): Neo4jGraph connection object
      input_text (str): rendom text from PDF or user input.
      model (str): AI model to use extraction from text

  Returns:
      data (list): list of lebels and relationTypes
  """
  result = schema_extraction_from_text(text, model, is_schema_description_cheked)
  return {"labels": result.labels, "relationshipTypes": result.relationshipTypes}