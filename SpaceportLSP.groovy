import spaceport.bridge.Command
import spaceport.computer.alerts.*
import spaceport.computer.alerts.results.*
import spaceport.personnel.Client
import spaceport.communications.http.launchpad.*
import spaceport.communications.http.*
import spaceport.communications.socket.*

import org.eclipse.jetty.websocket.api.RemoteEndpoint
import groovy.json.JsonOutput

//
// This file should be placed in your root module folder on Spaceport
//

class SpaceportLSP {

  // Current Connections
	static def sessions = []


	@Alert('on initialize')
	static _init(Result r) {
		Command.debug('SpaceportLSP initialized.')
	}


	@Alert('on socket connect')
	static _connect(Result r) {
		Command.debug('LSP Socket Open')

		Thread.start {
			Command.debug('Begin pinging client.')
			while (r.context.session.isOpen()) {
				Thread.sleep(10000)
				r.context.session.remote.sendPing()
				Command.debug('Ping? PONG.')
			}
			Command.debug('LSP socket closed.')
		}
		
		sessions.add(new SpaceportLSP(r.context.handler))
	}


	SocketHandler handler
	RemoteEndpoint endpoint


	@Alert('on socket SpaceportLSP')
	static spaceportLSP(SocketResult r) {
		// find the SpaceportLSP that corresponds to the handler
		SpaceportLSP lsp = sessions.find { it.handler == r.context.handler }
		if (lsp == null) {
			Command.error('Could not find SpaceportLSP for handler.')
			Command.println(r.context.handler.toString())
			Command.println(sessions.collect { it.handler.toString() })
			return
		} else {
      // Send along
			lsp.handleMessage(r.context.data)
		}			
	}


  //
  // INSTANCE
  //

  
	SpaceportLSP(SocketHandler handler) {
		this.handler = handler
		this.endpoint = handler.remote
	}


	// Handle message from the client
	void handleMessage(Map payload) {
		def jsonrpc = payload.jsonrpc
		def method = payload.method
		def params = payload.params

		// add id to params
		params.id = payload.id

		Command.debug("Received message: ${method}")

		if (method == 'initialize') 
			handleInitialize(params)
		else if (method == "textDocument/completion")
			handleCompletion(params)
		else if (method == "textDocument/hover")
			handleHover(params)
		else if (method == "textDocument/signatureHelp")
			handleSignatureHelp(params)
		else if (method == "textDocument/definition")
			handleDefinition(params)
		else if (method == "textDocument/references")
			handleReferences(params)
		else if (method == 'textDocument/didOpen')
			handleTextDocumentDidOpen(params)
		else if (method == 'textDocument/didChange')
			handleTextDocumentDidChange(params)
		else if (method == 'textDocument/didSave')
			handleTextDocumentDidSave(params)
		else if (method == 'textDocument/didClose')
			handleTextDocumentDidClose(params)
		else if (method == 'shutdown')
			handleShutdown()
		else if (method == 'exit')
			handleExit()
		else
			Command.error("Unknown method: ${method}")
	}


	// Handle initialize message
	void handleInitialize(Map params) {
		def capabilities = [
			textDocumentSync: 1,
			hoverProvider: true,
			completionProvider: [resolveProvider: true, triggerCharacters: ['.', ':']],
			signatureHelpProvider: [triggerCharacters: ['(', ',']],
			definitionProvider: true,
			referencesProvider: true,
			documentHighlightProvider: true,
			documentSymbolProvider: true,
			codeActionProvider: true,
			codeLensProvider: [resolveProvider: true],
			documentFormattingProvider: true,
			documentRangeFormattingProvider: true,
			documentOnTypeFormattingProvider: [firstTriggerCharacter: '}', moreTriggerCharacter: [';']],
			renameProvider: true,
			workspaceSymbolProvider: true
		]

		def response = [
			jsonrpc: '2.0',
			id: params.id,
			result: [
				capabilities: capabilities
			]
		]

		Command.debug("Sending initialize response.")
		endpoint.sendString(response as String)
	}

	def sourceFiles = [:]


	void handleTextDocumentDidOpen(Map params) {
		Command.debug("Received textDocument/didOpen.")
		sourceFiles.put(params.textDocument.uri, params.textDocument.text)
	}


	void handleTextDocumentDidChange(Map params) {
		Command.debug("Received textDocument/didChange.")
		sourceFiles.put(params.textDocument.uri, params.textDocument.text)
	}


	void handleTextDocumentDidSave(Map params) {
		Command.debug("Received textDocument/didSave.")
	}


	void handleTextDocumentDidClose(Map params) {
		Command.debug("Received textDocument/didClose.")
	}


	void handleShutdown() {
		Command.debug("Received shutdown.")
	}


	void handleExit() {
		Command.debug("Received exit.")
	}


	void handleCompletion(Map params) {
	    Command.debug("Received completion.")
	    Command.debug(params.toString())


	    def position = params.position
	    def context = params.context
	    def textDocument = params.textDocument
	    def uri = textDocument.uri
	    def fileName = new File(new URI(uri)).path  // Convert URI to file path

	    Command.debug("File Name: ${fileName}")

	    // 2. Get the actual 'Class' from referencing the file path/name
	    Class clazz = null;
	    try {
	        // Use GroovyClassLoader to load the class dynamically.  Crucial for runtime updates.
	        GroovyClassLoader groovyClassLoader = new GroovyClassLoader(this.getClass().getClassLoader())
	        clazz = groovyClassLoader.parseClass(new File(fileName))
	        Command.debug("Class Found: ${clazz.name}")
	    } catch (Exception e) {
	        Command.debug("Error loading class: ${e.getMessage()}")
	        sendError(endpoint, "Error loading class: " + e.getMessage());
	        return; // Exit if we can't load the class.
	    }
	     if (clazz == null) {
	          Command.debug("Class not found for ${fileName}")
	          return; 
	     }

	    // Gather Completion Items

	    List<Map> completionItems = []

	    // Get methods that are declared in the class
		
	    try{
	        clazz.declaredMethods.each { method ->
	            def completionItem = [
	                label: method.name + '(Method)',
	                kind: 6, //  Method (VS Code CompletionItemKind) - adjust as needed
	                detail: method.returnType.name + " " + method.name + "(" + method.parameterTypes.collect { it.name }.join(', ') + ")",
	                // documentation: getDocumentation(method), // Optional: Add Javadoc if available
	            	insertText: method.name + "(${method.parameterTypes.collect { it.name }.join(', ')})",
					sortText: method.name,
					filterText: method.name,
					data: [method: method.name, kind: 6]
	            ]
	            completionItems.add(completionItem)
	        }
	    } catch (Exception e){
	        e.printStackTrace()
	    }
	    
	    // Get fields that are declared in the class
	    try {
			clazz.declaredFields.each { field ->
				def completionItem = [
					label: field.name + '(Field)',
					kind: 9, // Field (VS Code CompletionItemKind) - adjust as needed
					detail: field.type.name + " " + field.name,
					// documentation: getDocumentation(field), // Optional: Add Javadoc if available
					insertText: field.name,
					sortText: field.name,
					filterText: field.name,
					data: [field: field.name, kind: 9]
				]

				completionItems.add(completionItem)
			}
		} catch (Exception e) {
			e.printStackTrace()
		}

	    // Sort Completion Items
	    completionItems = completionItems.sort { it.label }

	    // Build the Completion List Response
	    def response = [
	        jsonrpc: "2.0",
	        id: params.id, // Use the same ID as the request

	        result: [
	            isIncomplete: false, // Set to true if you have more completions to provide later.
	            items: completionItems
	        ]
	    ]

	    // 6. Send the Response via WebSocket
	    try {
	        endpoint.sendString(JsonOutput.toJson(response))
	        Command.debug ("Completion Performed, returning " + completionItems.size() + " results.")
	    } catch (IOException e) {
	        Command.debug("Error sending completion response: ${e.getMessage()}")
	    }
	}


	// Handle hover message
	void handleHover(Map params) {
		Command.debug("Received hover.")
	}


	// Handle signatureHelp message
	void handleSignatureHelp(Map params) {
		Command.debug("Received signatureHelp.")
	}

	// Handle definition message
	void handleDefinition(Map params) {
		Command.debug("Received definition.")
	}


	// Handle references message
	void handleReferences(Map params) {
		Command.debug("Received references.")
	}


}
