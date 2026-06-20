import React, { useEffect, useRef, useState } from 'react';
import { useGLTF } from '@react-three/drei';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

interface AgentAvatarProps {
  agentMessage: any;
}

export const AgentAvatar: React.FC<AgentAvatarProps> = ({ agentMessage }) => {
  // Use the female avatar available in the public directory
  const { scene } = useGLTF('/ready_player_me_female_avatar__vrchatgame.glb');
  
  const [isSpeaking, setIsSpeaking] = useState(false);
  const headMeshRef = useRef<THREE.SkinnedMesh | null>(null);

  // Traverse the scene to find the head mesh that has morph targets
  useEffect(() => {
    scene.traverse((child) => {
      if ((child as THREE.SkinnedMesh).isSkinnedMesh) {
        const mesh = child as THREE.SkinnedMesh;
        if (mesh.morphTargetDictionary && mesh.morphTargetInfluences) {
          // Typically the head/face mesh in Ready Player Me has mouth morph targets
          if (mesh.name.includes('Head') || mesh.name.includes('Face') || Object.keys(mesh.morphTargetDictionary).length > 0) {
            headMeshRef.current = mesh;
          }
        }
      }
    });
  }, [scene]);

  useEffect(() => {
    if (agentMessage && agentMessage.text_to_speak) {
      setIsSpeaking(true);
      
      // Estimate speaking duration (approx 150 words per minute -> 2.5 words per second)
      const wordCount = agentMessage.text_to_speak.split(' ').length;
      const durationMs = Math.max(1000, (wordCount / 2.5) * 1000);
      
      const timer = setTimeout(() => {
        setIsSpeaking(false);
      }, durationMs);
      
      return () => clearTimeout(timer);
    }
  }, [agentMessage]);

  useFrame(({ clock }) => {
    if (headMeshRef.current && headMeshRef.current.morphTargetInfluences && headMeshRef.current.morphTargetDictionary) {
      // Find the index for mouth open morph target
      const dict = headMeshRef.current.morphTargetDictionary;
      // RPM uses visemes, e.g., 'viseme_O', 'viseme_a', or 'mouthOpen'
      const targetKeys = ['mouthOpen', 'viseme_aa', 'viseme_O', 'jawOpen'];
      let targetIndex = -1;
      
      for (const key of targetKeys) {
        if (dict[key] !== undefined) {
          targetIndex = dict[key];
          break;
        }
      }

      if (targetIndex !== -1) {
        if (isSpeaking) {
          // Oscillate mouth open value using sine wave
          const t = clock.getElapsedTime();
          // Rapid movement to simulate talking
          const val = (Math.sin(t * 15) + 1) / 2 * 0.8; 
          headMeshRef.current.morphTargetInfluences[targetIndex] = val;
        } else {
          // Close mouth smoothly
          headMeshRef.current.morphTargetInfluences[targetIndex] = THREE.MathUtils.lerp(
            headMeshRef.current.morphTargetInfluences[targetIndex],
            0,
            0.2
          );
        }
      }
    }
  });

  return (
    <group dispose={null}>
      <primitive object={scene} scale={2.5} position={[0, -3.5, 0]} />
    </group>
  );
};

// Preload the model
useGLTF.preload('/ready_player_me_female_avatar__vrchatgame.glb');
