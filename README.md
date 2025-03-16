# spaceport-slt
Syntax Highlighting and LSP for Spaceport

This is a very early rendidtion of a Spaceport LSP. Under active development.

## Dependencies
Insert this entry into your repositories 'Package Control.sublime-settings' to fetch this from Package Control, and sastisfy the dependency of the websocket-client python library.

```
"repositories":
    [
    	"https://www.aufdem.dev/assets/sublime-packages.json",
    ],
```


## Embedded Blocks
Insert this entry into the 'rules' on your current color-scheme settings to enable color coded blocks when editing .ghtml files.

```
"rules":
	[
		{
			"name": "embedded.groovy",
			"scope": "embedded.groovy",
			"background": "color(black alpha(0.3))"
		},

		{
			"name": "embedded.closure",
			"scope": "embedded.closure",
			"background": "color(black alpha(0.8))"
		},

		{
			"name": "embedded.action",
			"scope": "embedded.action",
			"background": "color(teal alpha(0.2))"
		},

		{
			"name": "embedded.reaction",
			"scope": "embedded.reaction",
			"background": "color(purple alpha(0.2))"
		},

		{
			"name": "embedded.css",
			"scope": "embedded.css",
			"background": "color(black alpha(0.1))"
		}
	]
```
