package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"go/ast"
	"go/parser"
	"go/printer"
	"go/token"
	"os"
	"strings"
)

type StructInfo struct {
	Name   string            `json:"name"`
	Fields map[string]string `json:"fields"`
}

type SyncOp struct {
	Line int    `json:"line"`
	Op   string `json:"op"`
}

type FuncInfo struct {
	Name      string   `json:"name"`
	Signature string   `json:"signature"`
	Receiver  string   `json:"receiver,omitempty"`
	StartLine int      `json:"start_line"`
	EndLine   int      `json:"end_line"`
	Code      string   `json:"code"`
	Calls     []string `json:"calls"`
	CalledBy  []string `json:"called_by"`
	SyncOps   []SyncOp `json:"sync_ops"`
}

type AnalysisResult struct {
	Package    string       `json:"package"`
	File       string       `json:"file"`
	Imports    []string     `json:"imports"`
	FullSource string       `json:"full_source"`
	Structs    []StructInfo `json:"structs"`
	Functions  []FuncInfo   `json:"functions"`
}

func exprToString(fset *token.FileSet, expr ast.Expr) string {
	if expr == nil {
		return ""
	}
	var buf bytes.Buffer
	_ = printer.Fprint(&buf, fset, expr)
	return buf.String()
}

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "Usage: go run analyzer/extract.go <path-to-target.go>")
		os.Exit(1)
	}
	filePath := os.Args[1]
	srcBytes, err := os.ReadFile(filePath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error reading file: %v\n", err)
		os.Exit(1)
	}

	fset := token.NewFileSet()
	file, err := parser.ParseFile(fset, filePath, srcBytes, parser.ParseComments)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Parse error: %v\n", err)
		os.Exit(1)
	}

	res := AnalysisResult{
		Package:    file.Name.Name,
		File:       filePath,
		Imports:    []string{},
		FullSource: string(srcBytes),
		Structs:    []StructInfo{},
		Functions:  []FuncInfo{},
	}

	for _, imp := range file.Imports {
		res.Imports = append(res.Imports, strings.Trim(imp.Path.Value, `"`))
	}

	funcMap := make(map[string]*FuncInfo)
	var funcOrder []string

	// Pass 1: Extract Structs and Function Signatures
	for _, decl := range file.Decls {
		genDecl, ok := decl.(*ast.GenDecl)
		if ok && genDecl.Tok == token.TYPE {
			for _, spec := range genDecl.Specs {
				ts, ok := spec.(*ast.TypeSpec)
				if !ok {
					continue
				}
				st, ok := ts.Type.(*ast.StructType)
				if !ok {
					continue
				}
				sInfo := StructInfo{
					Name:   ts.Name.Name,
					Fields: make(map[string]string),
				}
				for _, field := range st.Fields.List {
					typeStr := exprToString(fset, field.Type)
					if len(field.Names) == 0 {
						sInfo.Fields[typeStr] = typeStr
					}
					for _, name := range field.Names {
						sInfo.Fields[name.Name] = typeStr
					}
				}
				res.Structs = append(res.Structs, sInfo)
			}
		}

		fnDecl, ok := decl.(*ast.FuncDecl)
		if !ok {
			continue
		}

		recv := ""
		if fnDecl.Recv != nil && len(fnDecl.Recv.List) > 0 {
			recv = exprToString(fset, fnDecl.Recv.List[0].Type)
		}

		startPos := fset.Position(fnDecl.Pos())
		endPos := fset.Position(fnDecl.End())
		codeSnippet := string(srcBytes[startPos.Offset:endPos.Offset])
		sigLine := strings.SplitN(codeSnippet, "{", 2)[0]

		fInfo := &FuncInfo{
			Name:      fnDecl.Name.Name,
			Signature: strings.TrimSpace(sigLine),
			Receiver:  recv,
			StartLine: startPos.Line,
			EndLine:   endPos.Line,
			Code:      codeSnippet,
			Calls:     []string{},
			CalledBy:  []string{},
			SyncOps:   []SyncOp{},
		}
		funcMap[fInfo.Name] = fInfo
		funcOrder = append(funcOrder, fInfo.Name)
	}

	syncKeywords := map[string]bool{
		"Lock": true, "Unlock": true, "RLock": true, "RUnlock": true,
		"Wait": true, "Signal": true, "Broadcast": true,
		"Add": true, "Done": true, "Load": true, "Store": true, "Do": true,
		"CompareAndSwap": true, "Swap": true, "Reset": true, "Stop": true, "close": true,
	}

	// Pass 2: Extract Call Graph Edges & Synchronization Primitives
	for _, decl := range file.Decls {
		fnDecl, ok := decl.(*ast.FuncDecl)
		if !ok || fnDecl.Body == nil {
			continue
		}
		callerName := fnDecl.Name.Name
		callerInfo := funcMap[callerName]
		seenCalls := make(map[string]bool)

		ast.Inspect(fnDecl.Body, func(n ast.Node) bool {
			switch node := n.(type) {
			case *ast.CallExpr:
				line := fset.Position(node.Pos()).Line
				callStr := exprToString(fset, node.Fun)
				calleeName := callStr
				if idx := strings.LastIndex(callStr, "."); idx != -1 {
					calleeName = callStr[idx+1:]
				}

				if syncKeywords[calleeName] {
					callerInfo.SyncOps = append(callerInfo.SyncOps, SyncOp{
						Line: line,
						Op:   callStr + "()",
					})
				}

				if targetFn, exists := funcMap[calleeName]; exists && calleeName != callerName {
					if !seenCalls[calleeName] {
						seenCalls[calleeName] = true
						callerInfo.Calls = append(callerInfo.Calls, calleeName)
						targetFn.CalledBy = append(targetFn.CalledBy, callerName)
					}
				}
			case *ast.SendStmt:
				line := fset.Position(node.Pos()).Line
				callerInfo.SyncOps = append(callerInfo.SyncOps, SyncOp{
					Line: line,
					Op:   exprToString(fset, node.Chan) + " <- send",
				})
			case *ast.UnaryExpr:
				if node.Op == token.ARROW {
					line := fset.Position(node.Pos()).Line
					callerInfo.SyncOps = append(callerInfo.SyncOps, SyncOp{
						Line: line,
						Op:   "<-" + exprToString(fset, node.X) + " recv",
					})
				}
			case *ast.GoStmt:
				line := fset.Position(node.Pos()).Line
				callerInfo.SyncOps = append(callerInfo.SyncOps, SyncOp{
					Line: line,
					Op:   "go spawn",
				})
			}
			return true
		})
	}

	for _, name := range funcOrder {
		res.Functions = append(res.Functions, *funcMap[name])
	}

	out, _ := json.MarshalIndent(res, "", "  ")
	fmt.Println(string(out))
}