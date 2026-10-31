import {Client} from '../vendor/3mf-mcp/node_modules/@modelcontextprotocol/sdk/dist/esm/client/index.js';
import {StdioClientTransport} from '../vendor/3mf-mcp/node_modules/@modelcontextprotocol/sdk/dist/esm/client/stdio.js';
import {fileURLToPath} from 'node:url';
const client=new Client({name:'printlint',version:'0.1.0'});
const transport=new StdioClientTransport({command:process.execPath,args:[fileURLToPath(new URL('../vendor/3mf-mcp/dist/cli.js',import.meta.url))],env:{...process.env,MCP_TRANSPORT:'stdio'},stderr:'pipe'});
function unwrap(r){if(r.isError)throw Error(r.content?.map(x=>x.text||'').join('\n'));return r.structuredContent||JSON.parse(r.content.find(x=>x.type==='text').text);}
try{
 await client.connect(transport);
 const compliance=unwrap(await client.callTool({name:'check_compliance',arguments:{path:process.argv[2]}}));
 const result={compliance};
 if(process.argv.includes('--full')){
  const loaded=unwrap(await client.callTool({name:'load_model',arguments:{path:process.argv[2]}}));result.loaded=loaded;
  const id=loaded.model_id||loaded.modelId;
  if(!id)throw Error('No model id: '+JSON.stringify(loaded));
  for(const name of ['inspect_model','list_objects','list_build_items','inspect_materials','validate_model']){
   result[name]=unwrap(await client.callTool({name,arguments:{model_id:id}}));
  }
 }
 process.stdout.write(JSON.stringify(result));
}catch(e){process.stderr.write(String(e));process.exitCode=2;}finally{await client.close();}
