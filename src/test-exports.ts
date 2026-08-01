import fs from 'fs';
import path from 'path';

console.log('\n=========================================');
console.log('🔍 DIAGNÓSTICO: ERROR DE REGISTRO DE APIS');
console.log('=========================================');

try {
  const codePath = 'node_modules/@mastra/core/dist/core.cjs.development.js';
  if (fs.existsSync(codePath)) {
    const content = fs.readFileSync(codePath, 'utf8');
    const lines = content.split('\n');
    
    console.log('📂 Ocurrencias de __registerApis y llamadas relacionadas:');
    console.log('-----------------------------------------');
    lines.forEach((line, index) => {
      if (line.includes('__registerApis') || line.includes('registerApis')) {
        console.log(`Línea ${index + 1}: ${line.trim().slice(0, 140)}`);
        
        const start = Math.max(0, index - 3);
        const end = Math.min(lines.length, index + 10);
        console.log(`--- Bloque de código (Líneas ${start + 1} a ${end}): ---`);
        for (let i = start; i < end; i++) {
          console.log(`   ${i + 1}: ${lines[i]}`);
        }
        console.log('----------------------------------------------------');
      }
    });

  } else {
    console.log('❌ No existe dist/core.cjs.development.js');
  }
} catch (e: any) {
  console.log('❌ Error al leer el código compilado:', e.message);
}

console.log('=========================================\n');
