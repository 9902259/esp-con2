"use strict";
import {fileURLToPath} from 'node:url';
import {dirname, resolve} from 'node:path';
import {mkdir, copyFile} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
// Compile TS and the reusable API together so the example's relative import stays portable.
const source = dirname(fileURLToPath(import.meta.url));
const root = resolve(source, '../../..');
const compiler = resolve(source, 'node_modules/typescript/bin/tsc');
const result = spawnSync(process.execPath, [compiler, '-p', resolve(source, 'tsconfig.json')], {stdio:'inherit'});
if (result.status !== 0) process.exit(result.status ?? 1);
await mkdir(resolve(root, 'build/js/example'), {recursive:true});
for (const file of ['index.html', 'style.css']) await copyFile(resolve(source,file), resolve(root,'build/js/example',file));
