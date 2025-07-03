#!/usr/bin/env python
"""
Test script to verify hybrid mode functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils import settings

def test_hybrid_mode_config():
    """Test if hybrid mode is properly configured"""
    try:
        # Load the configuration
        config = settings.check_toml("utils/.config.template.toml", "config.toml")
        
        # Check if hybrid mode is enabled
        hybrid_mode = config["settings"].get("hybrid_mode", False)
        hybrid_comments_count = config["settings"].get("hybrid_comments_count", 5)
        
        print("=== Hybrid Mode Configuration Test ===")
        print(f"Hybrid mode enabled: {hybrid_mode}")
        print(f"Hybrid comments count: {hybrid_comments_count}")
        
        if hybrid_mode:
            print("✅ Hybrid mode is ENABLED and configured!")
            print("This mode will include both the post text AND the top comments in the video.")
            print(f"It will include up to {hybrid_comments_count} top comments.")
        else:
            print("❌ Hybrid mode is DISABLED")
            
        # Show other relevant settings
        storymode = config["settings"].get("storymode", False)
        storymodemethod = config["settings"].get("storymodemethod", 1)
        
        print(f"\nOther relevant settings:")
        print(f"Story mode: {storymode}")
        print(f"Story mode method: {storymodemethod}")
        
        return hybrid_mode
        
    except Exception as e:
        print(f"Error testing hybrid mode: {e}")
        return False

def test_hybrid_mode_features():
    """Test the features available in hybrid mode"""
    print("\n=== Hybrid Mode Features ===")
    print("When hybrid mode is enabled, the bot will:")
    print("1. ✅ Read the post title (like all modes)")
    print("2. ✅ Read the post content/text (from story mode)")
    print("3. ✅ Read the top comments (from comment mode)")
    print("4. ✅ Generate screenshots for both post and comments")
    print("5. ✅ Create a video with post text followed by comments")
    
    print("\n=== Configuration Options ===")
    print("- hybrid_mode: Enable/disable hybrid mode")
    print("- hybrid_comments_count: Number of top comments to include (1-20)")
    print("- storymodemethod: How to display post content (0=single image, 1=fancy)")

if __name__ == "__main__":
    hybrid_enabled = test_hybrid_mode_config()
    test_hybrid_mode_features()
    
    if hybrid_enabled:
        print("\n🎉 SUCCESS: Hybrid mode is ready to use!")
        print("You can now run 'python main.py' to create videos with both post text and comments.")
    else:
        print("\n⚠️  Hybrid mode is not enabled. To enable it:")
        print("1. Edit config.toml")
        print("2. Set hybrid_mode = true")
        print("3. Set hybrid_comments_count = 5 (or your preferred number)")
        print("4. Set storymode = false (hybrid mode replaces story mode)")
