"""
IPFS Client for OBLIVION Workers
Handles file upload/download via Pinata or local IPFS node
"""
import os
import json
import httpx
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, Union
from dotenv import load_dotenv

load_dotenv()

class IPFSClient:
    """
    IPFS client supporting both Pinata (hosted) and local IPFS node
    """
    
    def __init__(self, use_pinata: bool = True):
        self.use_pinata = use_pinata
        
        if use_pinata:
            self.pinata_jwt = os.getenv('PINATA_JWT')
            self.pinata_api_key = os.getenv('PINATA_API_KEY')
            self.pinata_secret = os.getenv('PINATA_SECRET_KEY')
            self.pinata_gateway = os.getenv('PINATA_GATEWAY', 'https://gateway.pinata.cloud')
            self.base_url = 'https://api.pinata.cloud'
            
            if not self.pinata_jwt and not (self.pinata_api_key and self.pinata_secret):
                print("⚠️  Warning: No Pinata credentials found. Set PINATA_JWT or PINATA_API_KEY + PINATA_SECRET_KEY")
        else:
            self.ipfs_api_url = os.getenv('IPFS_API_URL', 'http://localhost:5001')
            self.ipfs_gateway = os.getenv('IPFS_GATEWAY', 'http://localhost:8080')
    
    def _get_headers(self) -> Dict[str, str]:
        """Get authentication headers for Pinata"""
        if self.pinata_jwt:
            return {'Authorization': f'Bearer {self.pinata_jwt}'}
        elif self.pinata_api_key and self.pinata_secret:
            return {
                'pinata_api_key': self.pinata_api_key,
                'pinata_secret_api_key': self.pinata_secret
            }
        return {}
    
    def upload_file(self, file_path: Union[str, Path], name: Optional[str] = None) -> Optional[str]:
        """
        Upload a file to IPFS
        Returns the IPFS CID (hash) or None on failure
        """
        file_path = Path(file_path)
        if not file_path.exists():
            print(f"❌ File not found: {file_path}")
            return None
        
        name = name or file_path.name
        
        try:
            if self.use_pinata:
                return self._upload_to_pinata(file_path, name)
            else:
                return self._upload_to_local_ipfs(file_path)
        except Exception as e:
            print(f"❌ Upload failed: {e}")
            return None
    
    def _upload_to_pinata(self, file_path: Path, name: str) -> Optional[str]:
        """Upload file to Pinata"""
        url = f"{self.base_url}/pinning/pinFileToIPFS"
        
        with open(file_path, 'rb') as f:
            files = {'file': (name, f)}
            metadata = json.dumps({'name': name})
            data = {'pinataMetadata': metadata}
            
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    url,
                    headers=self._get_headers(),
                    files=files,
                    data=data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    cid = result['IpfsHash']
                    print(f"✅ Uploaded to IPFS: {cid}")
                    return cid
                else:
                    print(f"❌ Pinata error: {response.status_code} - {response.text}")
                    return None
    
    def _upload_to_local_ipfs(self, file_path: Path) -> Optional[str]:
        """Upload file to local IPFS node"""
        url = f"{self.ipfs_api_url}/api/v0/add"
        
        with open(file_path, 'rb') as f:
            files = {'file': f}
            
            with httpx.Client(timeout=120.0) as client:
                response = client.post(url, files=files)
                
                if response.status_code == 200:
                    result = response.json()
                    cid = result['Hash']
                    print(f"✅ Uploaded to local IPFS: {cid}")
                    return cid
                else:
                    print(f"❌ IPFS error: {response.status_code}")
                    return None
    
    def upload_json(self, data: Dict[str, Any], name: str = "data.json") -> Optional[str]:
        """Upload JSON data to IPFS"""
        try:
            if self.use_pinata:
                return self._upload_json_to_pinata(data, name)
            else:
                # Write to temp file and upload
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                    json.dump(data, f)
                    temp_path = f.name
                
                result = self._upload_to_local_ipfs(Path(temp_path))
                os.unlink(temp_path)
                return result
        except Exception as e:
            print(f"❌ JSON upload failed: {e}")
            return None
    
    def _upload_json_to_pinata(self, data: Dict[str, Any], name: str) -> Optional[str]:
        """Upload JSON directly to Pinata"""
        url = f"{self.base_url}/pinning/pinJSONToIPFS"
        
        payload = {
            'pinataContent': data,
            'pinataMetadata': {'name': name}
        }
        
        headers = {**self._get_headers(), 'Content-Type': 'application/json'}
        
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                cid = result['IpfsHash']
                print(f"✅ JSON uploaded to IPFS: {cid}")
                return cid
            else:
                print(f"❌ Pinata JSON error: {response.status_code} - {response.text}")
                return None
    
    def download_file(self, cid: str, output_path: Union[str, Path]) -> bool:
        """
        Download a file from IPFS by CID
        Returns True on success, False on failure
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Clean CID (remove ipfs:// prefix if present)
        cid = cid.replace('ipfs://', '').strip()
        
        try:
            if self.use_pinata:
                url = f"{self.pinata_gateway}/ipfs/{cid}"
            else:
                url = f"{self.ipfs_gateway}/ipfs/{cid}"
            
            print(f"📥 Downloading from IPFS: {cid[:16]}...")
            
            with httpx.Client(timeout=120.0, follow_redirects=True) as client:
                response = client.get(url)
                
                if response.status_code == 200:
                    with open(output_path, 'wb') as f:
                        f.write(response.content)
                    print(f"✅ Downloaded to: {output_path}")
                    return True
                else:
                    print(f"❌ Download failed: {response.status_code}")
                    return False
        except Exception as e:
            print(f"❌ Download error: {e}")
            return False
    
    def download_json(self, cid: str) -> Optional[Dict[str, Any]]:
        """Download JSON data from IPFS"""
        cid = cid.replace('ipfs://', '').strip()
        
        try:
            if self.use_pinata:
                url = f"{self.pinata_gateway}/ipfs/{cid}"
            else:
                url = f"{self.ipfs_gateway}/ipfs/{cid}"
            
            with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                response = client.get(url)
                
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"❌ JSON download failed: {response.status_code}")
                    return None
        except Exception as e:
            print(f"❌ JSON download error: {e}")
            return None
    
    def pin_cid(self, cid: str, name: Optional[str] = None) -> bool:
        """Pin an existing CID to keep it available"""
        if not self.use_pinata:
            # Local IPFS - use pin add
            url = f"{self.ipfs_api_url}/api/v0/pin/add?arg={cid}"
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url)
                return response.status_code == 200
        
        url = f"{self.base_url}/pinning/pinByHash"
        payload = {'hashToPin': cid}
        if name:
            payload['pinataMetadata'] = {'name': name}
        
        headers = {**self._get_headers(), 'Content-Type': 'application/json'}
        
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=payload)
            return response.status_code == 200
    
    def get_gateway_url(self, cid: str) -> str:
        """Get the gateway URL for a CID"""
        cid = cid.replace('ipfs://', '').strip()
        if self.use_pinata:
            return f"{self.pinata_gateway}/ipfs/{cid}"
        return f"{self.ipfs_gateway}/ipfs/{cid}"
    
    def test_connection(self) -> bool:
        """Test IPFS connection"""
        try:
            if self.use_pinata:
                url = f"{self.base_url}/data/testAuthentication"
                with httpx.Client(timeout=10.0) as client:
                    response = client.get(url, headers=self._get_headers())
                    if response.status_code == 200:
                        print("✅ Pinata connection successful")
                        return True
                    else:
                        print(f"❌ Pinata auth failed: {response.status_code}")
                        return False
            else:
                url = f"{self.ipfs_api_url}/api/v0/id"
                with httpx.Client(timeout=10.0) as client:
                    response = client.post(url)
                    if response.status_code == 200:
                        print("✅ Local IPFS connection successful")
                        return True
                    else:
                        print(f"❌ Local IPFS failed: {response.status_code}")
                        return False
        except Exception as e:
            print(f"❌ Connection test failed: {e}")
            return False


class MockIPFSClient:
    """
    Mock IPFS client for testing without network
    Stores files locally with hash-based naming
    """
    
    def __init__(self, storage_dir: str = "./ipfs_mock"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = self.storage_dir / "metadata.json"
        self.metadata = self._load_metadata()
    
    def _load_metadata(self) -> Dict[str, Any]:
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_metadata(self):
        with open(self.metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)
    
    def _compute_hash(self, data: bytes) -> str:
        """Compute a mock IPFS-like hash"""
        h = hashlib.sha256(data).hexdigest()
        return f"Qm{h[:44]}"  # Mock CID format
    
    def upload_file(self, file_path: Union[str, Path], name: Optional[str] = None) -> Optional[str]:
        file_path = Path(file_path)
        if not file_path.exists():
            return None
        
        with open(file_path, 'rb') as f:
            data = f.read()
        
        cid = self._compute_hash(data)
        
        # Store file
        stored_path = self.storage_dir / cid
        with open(stored_path, 'wb') as f:
            f.write(data)
        
        # Update metadata
        self.metadata[cid] = {
            'name': name or file_path.name,
            'size': len(data),
            'type': 'file'
        }
        self._save_metadata()
        
        print(f"✅ [MOCK] Uploaded to IPFS: {cid}")
        return cid
    
    def upload_json(self, data: Dict[str, Any], name: str = "data.json") -> Optional[str]:
        json_bytes = json.dumps(data).encode()
        cid = self._compute_hash(json_bytes)
        
        stored_path = self.storage_dir / cid
        with open(stored_path, 'wb') as f:
            f.write(json_bytes)
        
        self.metadata[cid] = {'name': name, 'size': len(json_bytes), 'type': 'json'}
        self._save_metadata()
        
        print(f"✅ [MOCK] JSON uploaded to IPFS: {cid}")
        return cid
    
    def download_file(self, cid: str, output_path: Union[str, Path]) -> bool:
        cid = cid.replace('ipfs://', '').strip()
        stored_path = self.storage_dir / cid
        
        if not stored_path.exists():
            print(f"❌ [MOCK] CID not found: {cid}")
            return False
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(stored_path, 'rb') as src:
            with open(output_path, 'wb') as dst:
                dst.write(src.read())
        
        print(f"✅ [MOCK] Downloaded to: {output_path}")
        return True
    
    def download_json(self, cid: str) -> Optional[Dict[str, Any]]:
        cid = cid.replace('ipfs://', '').strip()
        stored_path = self.storage_dir / cid
        
        if not stored_path.exists():
            return None
        
        with open(stored_path, 'r') as f:
            return json.load(f)
    
    def get_gateway_url(self, cid: str) -> str:
        return f"file://{self.storage_dir}/{cid}"
    
    def test_connection(self) -> bool:
        print("✅ [MOCK] IPFS client ready (local storage)")
        return True


def get_ipfs_client(use_mock: bool = False) -> Union[IPFSClient, MockIPFSClient]:
    """
    Factory function to get appropriate IPFS client
    
    Priority:
    1. If use_mock=True, return MockIPFSClient
    2. If PINATA_JWT or PINATA_API_KEY set, use Pinata
    3. If IPFS_API_URL set, use local IPFS
    4. Fall back to mock
    """
    if use_mock:
        return MockIPFSClient()
    
    # Check for Pinata credentials
    if os.getenv('PINATA_JWT') or os.getenv('PINATA_API_KEY'):
        client = IPFSClient(use_pinata=True)
        if client.test_connection():
            return client
    
    # Check for local IPFS
    if os.getenv('IPFS_API_URL'):
        client = IPFSClient(use_pinata=False)
        if client.test_connection():
            return client
    
    # Fall back to mock
    print("⚠️  No IPFS service available, using mock client")
    return MockIPFSClient()


if __name__ == "__main__":
    # Test the client
    print("Testing IPFS Client...")
    
    client = get_ipfs_client(use_mock=True)
    
    # Test JSON upload
    test_data = {"model": "test", "accuracy": 0.95}
    cid = client.upload_json(test_data, "test_model.json")
    
    if cid:
        # Test download
        downloaded = client.download_json(cid)
        print(f"Downloaded data: {downloaded}")
        
        # Test gateway URL
        url = client.get_gateway_url(cid)
        print(f"Gateway URL: {url}")
