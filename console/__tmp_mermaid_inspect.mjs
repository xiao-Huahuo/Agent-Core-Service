import mermaid from 'mermaid'
import { JSDOM } from 'jsdom'

const dom = new JSDOM('<div id="root"></div>')
global.window = dom.window
global.document = dom.window.document
global.Element = dom.window.Element
global.HTMLElement = dom.window.HTMLElement
global.SVGElement = dom.window.SVGElement

document.body.innerHTML = '<div id="root"></div>'
mermaid.initialize({ startOnLoad: false, theme: 'dark', flowchart: { useMaxWidth: true, htmlLabels: true, curve: 'basis' } })
const code = `flowchart TD
    safety_input["safety_input"]
    compress["compress"]
    planner["planner"]
    agent["agent"]
    action["action"]
    reflection["reflection"]
    safety_output["safety_output"]
    safety_input -->|"通过"| compress
    safety_input -->|"拦截"| E1((END))
    compress --> planner
    planner --> agent
    agent -->|"工具调用"| action
    agent -->|"直接回复"| safety_output
    action --> reflection
    reflection -->|"继续/回答"| planner
    reflection -->|"上下文溢出"| compress
    safety_output --> E2((END))`
const { svg } = await mermaid.render('langgraph-svg', code)
console.log(svg)
