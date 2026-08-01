import dotenv from 'dotenv';
import { z } from 'zod';

dotenv.config();

const envSchema = z.object({
  PORT: z.string().default('3000'),
  GROQ_API_KEY: z.string().min(1, 'La API key de Groq (GROQ_API_KEY) es requerida para el procesamiento gratuito'),
});

const parsedEnv = envSchema.safeParse(process.env);

if (!parsedEnv.success) {
  console.error('⚠️ Error en las variables de entorno:', parsedEnv.error.format());
  process.exit(1);
}

export const config = {
  PORT: parseInt(parsedEnv.data.PORT, 10),
  GROQ_API_KEY: parsedEnv.data.GROQ_API_KEY,
};
